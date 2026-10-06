# NutriLens

NutriLens is an AI vision nutrition chatbot built with Streamlit, Google's
`google-genai` SDK, Pydantic, and Twilio. Upload or take a meal photo to get
estimated nutrition, ask follow-up questions, and send a concise summary to
WhatsApp.

Nutrition estimates from photos are approximate and are not medical advice.

## Requirements

- Python 3.10 or newer
- A Gemini API key
- Twilio account credentials to send WhatsApp messages

## Run locally

1. Open a terminal in the project folder and create a virtual environment:

   ```powershell
   python -m venv .venv
   ```

2. Activate the environment:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, allow scripts for this terminal session:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and
   replace its placeholder values with your credentials. Get a Gemini API key
   at [Google AI Studio](https://aistudio.google.com/apikey).

5. Start the app:

   ```powershell
   streamlit run app.py
   ```

## Configure Twilio WhatsApp Sandbox

1. Sign in to Twilio and open **Messaging > Try it out > Send a WhatsApp
   message** to enable the WhatsApp Sandbox.
2. Follow the sandbox instructions to join from your WhatsApp account. The
   phone that will receive messages must first send **`join <code>`** to the
   sandbox number shown in Twilio.
3. Add the Twilio Account SID and Auth Token from your Twilio Console to
   `.streamlit/secrets.toml`. Set `TWILIO_WHATSAPP_FROM` to the sandbox sender
   (usually `whatsapp:+14155238886`).
4. Enter the joined WhatsApp number in NutriLens using the format
   `+91XXXXXXXXXX`, then choose **Summarise & send**.

The default sender is the Twilio WhatsApp Sandbox number. A production
WhatsApp sender requires an approved Twilio WhatsApp setup.

## Deploy on Streamlit Community Cloud

1. Push the project to a GitHub repository. Do not commit
   `.streamlit/secrets.toml`; it is excluded by `.gitignore`.
2. Go to [share.streamlit.io](https://share.streamlit.io/), sign in with
   GitHub, and deploy the repository with `app.py` as the main file.
3. Open the app's **Advanced settings > Secrets** and paste the TOML-formatted
   secret values from your local secrets file. Never publish your keys.
4. Save and deploy. Streamlit Cloud installs the packages listed in
   `requirements.txt`.
