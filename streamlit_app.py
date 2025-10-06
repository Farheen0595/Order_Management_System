import streamlit as st
import asyncio
from app.utils.streamlit_functions import initialize_sessions, handle_master_agent

# ----------------- PAGE CONFIG -----------------
st.set_page_config(page_title="Agentic Order Management System", layout="wide")

st.title("Order Management Agent")


# Initialize session and show ID
session_id = initialize_sessions()
# st.write(f"Current Session ID: {session_id}")



# Display past messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])



# Chat input
if prompt := st.chat_input("Ask your Query"):
    # Show user's message
    with st.chat_message("user"):
        st.markdown(prompt)


    st.session_state.messages.append({"role": "user", "content": prompt})

    try:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = asyncio.run(handle_master_agent(user_query=prompt))
          
                st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})

    except Exception as e:
        error_message = f"I encountered an issue: {e}"
        print(f"[DEBUG ERROR] {e}")
        st.error(error_message)
        st.session_state.messages.append({"role": "assistant", "content": error_message})
