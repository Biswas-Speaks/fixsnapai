import json

import streamlit as st
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient

from prompts import SYSTEM_PROMPT, WELCOME_MESSAGE


# ============================================================
# BASIC SETTINGS
# ============================================================

MODEL_NAME = "gemini-2.5-flash"

st.set_page_config(
    page_title="FixSnap AI",
    page_icon="🔧",
    layout="centered",
)


# ============================================================
# API KEYS
# ============================================================

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]
TWILIO_CONTENT_SID = st.secrets["TWILIO_CONTENT_SID"]


# ============================================================
# GEMINI
# ============================================================

@st.cache_resource
def get_gemini_client():

    return genai.Client(
        api_key=GEMINI_API_KEY
    )


gemini = get_gemini_client()


# ============================================================
# SESSION DATA
# ============================================================

if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_ai_response" not in st.session_state:
    st.session_state.last_ai_response = None


# ============================================================
# DISPLAY MESSAGE
# ============================================================

def show_message(message):

    with st.chat_message(message["role"]):

        if message["type"] == "text":

            st.markdown(
                message["content"]
            )

        elif message["type"] == "image":

            st.image(
                message["content"],
                use_container_width=True
            )


# ============================================================
# ADD MESSAGE
# ============================================================

def add_message(role, message_type, content):

    message = {
        "role": role,
        "type": message_type,
        "content": content
    }

    st.session_state.messages.append(
        message
    )

    show_message(message)


# ============================================================
# ASK GEMINI
# ============================================================

def ask_gemini(parts):

    try:

        response = st.session_state.chat.send_message(
            parts
        )

        if response and response.text:

            return response.text

        return "Hmm, I couldn't figure that out."

    except Exception as error:

        print("Gemini Error:", error)

        return (
            "Sorry 😅 something went wrong while "
            "I was trying to understand the problem."
        )


# ============================================================
# SEND WHATSAPP
# ============================================================

def send_whatsapp(phone_number, name, answer):

    try:

        twilio = TwilioClient(
            TWILIO_ACCOUNT_SID,
            TWILIO_AUTH_TOKEN
        )

        # Keep WhatsApp message reasonably short.
        answer = " ".join(
            answer.split()
        )

        if len(answer) > 1500:

            answer = answer[:1500] + "..."

        variables = json.dumps(
            {
                "1": name,
                "2": answer
            },
            ensure_ascii=False
        )

        message = twilio.messages.create(

            from_=TWILIO_WHATSAPP_FROM,

            to=f"whatsapp:{phone_number}",

            content_sid=TWILIO_CONTENT_SID,

            content_variables=variables
        )

        return True, message.sid

    except Exception as error:

        print("WhatsApp Error:", error)

        return False, None


# ============================================================
# FIRST SCREEN
# ============================================================

if not st.session_state.onboarded:

    st.title("🔧 FixSnap AI")

    st.write(
        "Snap a photo. Show me the problem. "
        "I'll try to help you fix it."
    )

    st.divider()

    with st.form("user_form"):

        name = st.text_input(
            "What's your name?",
            placeholder="Example: Biswas"
        )

        phone = st.text_input(
            "WhatsApp Number",
            placeholder="+91XXXXXXXXXX"
        )

        start = st.form_submit_button(
            "Let's Start 🚀",
            use_container_width=True
        )

    if start:

        if not name.strip():

            st.warning(
                "Please enter your name."
            )

        elif not phone.strip():

            st.warning(
                "Please enter your WhatsApp number."
            )

        else:

            st.session_state.name = (
                name.strip()
            )

            st.session_state.phone = (
                phone.strip()
            )

            # Start Gemini chat
            st.session_state.chat = (
                gemini.chats.create(

                    model=MODEL_NAME,

                    config=types.GenerateContentConfig(

                        system_instruction=SYSTEM_PROMPT
                    )
                )
            )

            st.session_state.onboarded = True

            st.rerun()

    st.stop()


# ============================================================
# MAIN HEADER
# ============================================================

col1, col2 = st.columns(
    [3, 2]
)

with col1:

    st.title("🔧 FixSnap AI")

with col2:

    if st.session_state.last_ai_response:

        if st.button(
            "📱 Send to WhatsApp",
            use_container_width=True
        ):

            with st.spinner(
                "Sending..."
            ):

                success, sid = send_whatsapp(

                    st.session_state.phone,

                    st.session_state.name,

                    st.session_state.last_ai_response
                )

            if success:

                st.success(
                    "Sent to WhatsApp 📲"
                )

            else:

                st.error(
                    "Couldn't send the message."
                )


st.caption(
    f"Hi {st.session_state.name} 👋"
)


# ============================================================
# SHOW OLD CHAT
# ============================================================

if not st.session_state.messages:

    add_message(
        "assistant",
        "text",
        WELCOME_MESSAGE.format(
            name=st.session_state.name
        )
    )

else:

    for message in st.session_state.messages:

        show_message(message)


# ============================================================
# CHAT INPUT
# ============================================================

user_message = st.chat_input(
    "Tell me what's wrong...",
    accept_file=True,
    file_type=[
        "jpg",
        "jpeg",
        "png",
        "webp"
    ]
)


# ============================================================
# USER MESSAGE
# ============================================================

if user_message:

    text = user_message.text

    photo = None

    if user_message.files:

        photo = user_message.files[0]


    # --------------------------------------------------------
    # SEND IMAGE TO CHAT
    # --------------------------------------------------------

    if photo:

        image_bytes = photo.getvalue()

        add_message(
            "user",
            "image",
            image_bytes
        )


    # --------------------------------------------------------
    # SEND TEXT TO CHAT
    # --------------------------------------------------------

    if text:

        add_message(
            "user",
            "text",
            text
        )


    # --------------------------------------------------------
    # PREPARE GEMINI REQUEST
    # --------------------------------------------------------

    parts = []


    if photo:

        image_bytes = photo.getvalue()

        parts.append(

            types.Part.from_bytes(

                data=image_bytes,

                mime_type=photo.type
            )
        )


    if text:

        parts.append(text)


    elif photo:

        parts.append(
            """
Look at this photo and try to understand
what might be wrong.

Explain it to me in simple language.

Tell me:

- What you notice
- What you think might be wrong
- What I can try
- If I should send another photo

Please don't sound like a professional
technical report. Talk normally, like a
helpful person.
"""
        )


    # --------------------------------------------------------
    # ASK AI
    # --------------------------------------------------------

    if parts:

        with st.spinner(
            "Hmm... let me have a look 👀"
        ):

            answer = ask_gemini(
                parts
            )


        # Show answer
        add_message(
            "assistant",
            "text",
            answer
        )


        # Save answer
        st.session_state.last_ai_response = answer

        st.rerun()