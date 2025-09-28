import streamlit as st
from app.utils.streamlit_functions import initialize_sessions, handle_master_agent
import asyncio




# ----------------- PAGE CONFIG -----------------
st.set_page_config(page_title="Agentic Order Management System", layout="wide")

st.title("🤖 Master Order Agent")



# Initialize sessions
initialize_sessions()




# Show history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Ask your Query"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        response = asyncio.run(handle_master_agent(user_query=prompt))
    except Exception as e:
        response = f" I encountered an issue: {e}"
        print(f"[DEBUG] {e}")

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
