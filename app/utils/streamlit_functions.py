import streamlit as st
import requests
import uuid
import httpx
from app.config.settings import settings
from app.config.loggings import setup_logging
import logging
import asyncio
from sqlalchemy import text
from app.database.engine import AsyncSessionLocal
from app.database.models import UserSessions
from streamlit_cookies_manager import EncryptedCookieManager


setup_logging(level=logging.INFO)
logger = logging.getLogger(__file__)


# ------------ PARAMETERS -------------------------
MASTER_AGENT_URL = settings.MASTER_AGENT_URL
SESSION_ID_URL = settings.SESSION_ID_URL
COOKIE_PASSWORD = settings.COOKIE_SECRET


# ---------------------- Session Initialization ----------------------

def initialize_sessions():

    """
    Initialize Streamlit session state variables.
    - Creates or restores session_id.
    - Persists session_id in URL query params so it survives refresh.

    """


    cookies = EncryptedCookieManager(prefix="oms_", password=COOKIE_PASSWORD)

    if not cookies.ready():
        st.stop()

    # --- Handle session_id ---

    if "session_id" not in cookies:

        resp = requests.get(SESSION_ID_URL)

        if resp.status_code == 200:

            new_session = resp.json()["session_id"]

            cookies["session_id"] = new_session

            cookies.save()  

            st.session_state["session_id"] = new_session

            # st.write(" New session started and saved in cookie.")
        else:

            st.error(f"Failed to start session: {resp.status_code} {resp.text}")

    else:

        st.session_state["session_id"] = cookies["session_id"]

        # st.write(f"Restored session from cookie: {cookies['session_id']}")
            


    if "messages" not in st.session_state:

        st.session_state.messages = []

    
    return st.session_state["session_id"]



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

        st.session_state["session_id"] = result.get(
            "session_id", st.session_state["session_id"]
            )
        return ans
    
    else:
        st.error(f" Error: {resp.status_code} {resp.text}")
        return None
