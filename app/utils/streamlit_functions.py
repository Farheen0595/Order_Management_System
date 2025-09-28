import streamlit as st
import uuid
import httpx
from app.config.settings import settings

# ------------ PARAMETERS -------------------------
MASTER_AGENT_URL = settings.MASTER_AGENT_URL


# ---------------------- Session Initialization ----------------------
def initialize_sessions():

    """
    Initialize Streamlit session state variables.
    """

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "messages" not in st.session_state:
        st.session_state.messages = []



async def handle_master_agent(user_query: str):

    """
    Handles sending a query to the master agent API (async).
    """

    if not user_query:
        return None

    payload = {
        "user_input": user_query,
        "session_id": st.session_state["session_id"],}


    try:
        async with httpx.AsyncClient(timeout=200) as client:
            resp = await client.post(MASTER_AGENT_URL, json=payload)

    except httpx.RequestError as e:
        st.error(f" Request failed: {e}")
        return None

    if resp.status_code == 200:
        result = resp.json()
        ans = result.get("output", " No answer generated.")

        # Update session ID if backend enforces it
        st.session_state["session_id"] = result.get(
            "session_id", st.session_state["session_id"]
        )

        # Display + store
        st.markdown(ans)
        st.session_state["messages"].append({"role": "assistant", "content": ans})

        return ans
    
    else:
        st.error(f" Error: {resp.status_code} {resp.text}")
        return None
