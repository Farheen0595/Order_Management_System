import streamlit as st
import asyncio
from app.utils.streamlit_functions import initialize_sessions, handle_master_agent
import logging
from app.config.loggings import setup_logging

setup_logging()

logger = logging.getLogger("app.streamlit_app")

# ----------------- PAGE CONFIG -----------------
st.set_page_config(page_title="SmartOrder AI - Agentic Order Management System",page_icon="🤖",layout="wide")

st.title("Order Management System - Agentic AI 🤖")
logger.info("Streamlit app started")


# Initialize session
session_id = initialize_sessions()
logger.info(f"Session initialized with ID: {session_id}")

# Display past messages
for msg in st.session_state.messages:

    avatar = "🤖" if msg["role"] == "assistant" else "🧑‍💻"

    with st.chat_message(msg["role"], avatar=avatar):

        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Ask your Query"):

    # User message with avatar
    with st.chat_message("user", avatar="🧑‍💻"):

        st.markdown(prompt)

    st.session_state.messages.append({"role": "user",
                                       "content": prompt})

    try:

        with st.chat_message("assistant", avatar="🤖"):

            with st.spinner("Thinking..."):

                response = asyncio.run(handle_master_agent(user_query=prompt))

                st.markdown(response)

        st.session_state.messages.append({"role": "assistant", 
                                          "content": response})

    except Exception as e:

        error_message = f"I encountered an issue: {e}"

        st.error(error_message)

        st.session_state.messages.append({"role": "assistant", "content": error_message})
