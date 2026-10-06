import hashlib
import os
import re
from typing import Literal

import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from streamlit.errors import StreamlitSecretNotFoundError
from twilio.rest import Client as TwilioClient


st.set_page_config(page_title="NutriLens", page_icon="🥗")


def get_setting(name: str, default: str | None = None) -> str | None:
    """Read a setting from Streamlit secrets, then fall back to the environment."""
    try:
        value = st.secrets.get(name)
    except StreamlitSecretNotFoundError:
        value = None

    if value is not None and str(value).strip():
        return str(value)
    return os.getenv(name, default)


class Item(BaseModel):
    name: str
    portion: str
    calories: int = Field(ge=0)


class Meal(BaseModel):
    dish: str
    items: list[Item]
    calories: int = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    fiber_g: float = Field(ge=0)
    health_note: str
    confidence: Literal["low", "medium", "high"]


ANALYSIS_PROMPT = (
    "Identify the meal in this photo and each visible food item. Estimate each item's "
    "portion and calories, and the meal's total calories, protein, carbohydrates, fat, "
    "and fibre in grams. Add a short, practical health note and rate your confidence "
    "as low, medium, or high. All nutrition values must be realistic estimates based "
    "only on what is visible in the photo."
)

CHAT_INSTRUCTION = (
    "You are NutriLens, a friendly nutrition assistant. Answer questions about the "
    "analysed meal briefly and clearly. Explain that photo-based nutrition numbers are "
    "estimates, and remind the user that you are not a doctor."
)


def analyse_meal(
    client: genai.Client, image_bytes: bytes, mime_type: str, model_name: str
) -> Meal:
    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ANALYSIS_PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Meal,
        ),
    )
    if response.parsed is None:
        raise ValueError("Gemini did not return structured meal analysis.")
    return Meal.model_validate(response.parsed)


def create_meal_chat(
    client: genai.Client,
    image_bytes: bytes,
    mime_type: str,
    meal: Meal,
    model_name: str,
):
    history = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(text="Please analyse this meal."),
            ],
        ),
        types.Content(
            role="model",
            parts=[types.Part.from_text(text=meal.model_dump_json())],
        ),
    ]
    return client.chats.create(
        model=model_name,
        history=history,
        config=types.GenerateContentConfig(system_instruction=CHAT_INSTRUCTION),
    )


def create_summary(
    client: genai.Client, meal: Meal, messages: list[dict[str, str]], model_name: str
) -> str:
    transcript = "\n".join(
        f"{message['role']}: {message['content']}" for message in messages
    )
    prompt = (
        "Write a WhatsApp-friendly plain-text summary under 900 characters, using a few "
        "emojis if useful. Cover the dish, estimated calories and macros, and key advice "
        "from the chat. Mention that photo-based nutrition figures are estimates. "
        "Do not give a diagnosis.\n\n"
        f"Meal analysis:\n{meal.model_dump_json()}\n\n"
        f"Chat:\n{transcript or '(No chat questions yet.)'}"
    )
    response = client.models.generate_content(model=model_name, contents=prompt)
    if not response.text or not response.text.strip():
        raise ValueError("Gemini returned an empty summary.")
    return response.text.strip()[:899]


def send_whatsapp(to_number: str, body: str, account_sid: str, auth_token: str, from_number: str):
    twilio = TwilioClient(account_sid, auth_token)
    return twilio.messages.create(
        from_=from_number,
        to=f"whatsapp:{to_number}",
        body=body[:1500],
    )


st.title("🥗 NutriLens")
st.caption(
    "Snap a meal, explore its estimated nutrition, chat with your AI assistant, "
    "and send yourself a summary."
)

gemini_api_key = get_setting("GEMINI_API_KEY")
if not gemini_api_key:
    st.error(
        "GEMINI_API_KEY is missing. Add it to `.streamlit/secrets.toml` locally "
        "or to your Streamlit Community Cloud app secrets."
    )
    st.stop()

model_name = get_setting("GEMINI_MODEL", "gemini-3.5-flash-lite")
twilio_account_sid = get_setting("TWILIO_ACCOUNT_SID")
twilio_auth_token = get_setting("TWILIO_AUTH_TOKEN")
twilio_whatsapp_from = get_setting(
    "TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"
)
client = genai.Client(api_key=gemini_api_key)

upload_tab, camera_tab = st.tabs(["Upload photo", "Use camera"])
with upload_tab:
    uploaded_image = st.file_uploader(
        "Choose a meal photo", type=["jpg", "jpeg", "png", "webp"]
    )
with camera_tab:
    camera_image = st.camera_input("Take a photo of your meal")

image = uploaded_image if uploaded_image is not None else camera_image
if image is None:
    st.info("Upload or take a meal photo to get started.")
    st.stop()

image_bytes = image.getvalue()
mime_type = image.type or "image/jpeg"
image_hash = hashlib.sha256(image_bytes).hexdigest()

# A new image starts a fresh analysis, chat, and summary.
if st.session_state.get("image_hash") != image_hash:
    for key in ("meal", "meal_chat", "messages", "summary"):
        st.session_state.pop(key, None)
    st.session_state["image_hash"] = image_hash

if "meal" not in st.session_state:
    with st.spinner("Analysing your meal..."):
        try:
            meal = analyse_meal(client, image_bytes, mime_type, model_name)
            meal_chat = create_meal_chat(
                client, image_bytes, mime_type, meal, model_name
            )
        except Exception as error:
            st.session_state.pop("image_hash", None)
            st.error(f"We couldn't analyse this photo. Please try again. Details: {error}")
            st.stop()
    st.session_state["meal"] = meal
    st.session_state["meal_chat"] = meal_chat
    st.session_state["messages"] = []

meal = st.session_state["meal"]

st.image(image_bytes, use_container_width=True)
st.subheader(meal.dish)
st.caption(f"Analysis confidence: {meal.confidence}")

calorie_col, protein_col, carbs_col, fat_col, fibre_col = st.columns(5)
calorie_col.metric("Calories", f"{meal.calories} kcal")
protein_col.metric("Protein", f"{meal.protein_g:g} g")
carbs_col.metric("Carbs", f"{meal.carbs_g:g} g")
fat_col.metric("Fat", f"{meal.fat_g:g} g")
fibre_col.metric("Fibre", f"{meal.fiber_g:g} g")

st.dataframe(
    [
        {"Item": item.name, "Portion": item.portion, "Calories": item.calories}
        for item in meal.items
    ],
    use_container_width=True,
    hide_index=True,
)
st.info(meal.health_note)

st.divider()
st.subheader("Chat about this meal")
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask a question about this meal")
if question:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = st.session_state["meal_chat"].send_message(question)
                answer = response.text
                if not answer:
                    raise ValueError("The assistant returned an empty response.")
            except Exception as error:
                st.error(f"We couldn't get an answer. Please try again. Details: {error}")
            else:
                st.markdown(answer)
                st.session_state["messages"].extend(
                    [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": answer},
                    ]
                )

st.divider()
st.subheader("Send a summary to WhatsApp")
phone_number = st.text_input(
    "WhatsApp number", placeholder="+91XXXXXXXXXX"
)
if st.button("Summarise & send", type="primary"):
    if not re.fullmatch(r"\+91\d{10}", phone_number.strip()):
        st.error("Enter a valid Indian mobile number in the format +91XXXXXXXXXX.")
    elif not twilio_account_sid or not twilio_auth_token:
        st.error(
            "Twilio credentials are missing. Add TWILIO_ACCOUNT_SID and "
            "TWILIO_AUTH_TOKEN to your secrets."
        )
    else:
        st.session_state.pop("summary", None)
        with st.spinner("Creating your summary..."):
            try:
                st.session_state["summary"] = create_summary(
                    client, meal, st.session_state["messages"], model_name
                )
            except Exception as error:
                st.error(
                    f"We couldn't create the summary. Please try again. Details: {error}"
                )

        if st.session_state.get("summary"):
            with st.spinner("Sending your WhatsApp message..."):
                try:
                    send_whatsapp(
                        phone_number.strip(),
                        st.session_state["summary"],
                        twilio_account_sid,
                        twilio_auth_token,
                        twilio_whatsapp_from,
                    )
                except Exception as error:
                    st.error(
                        "The summary was created, but WhatsApp could not send it. "
                        f"Check your Twilio setup and number. Details: {error}"
                    )
                else:
                    st.success("Summary sent! Check your WhatsApp messages.")

if st.session_state.get("summary"):
    st.text_area("WhatsApp summary", st.session_state["summary"], height=160)
