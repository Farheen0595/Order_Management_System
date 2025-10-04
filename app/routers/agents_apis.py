import logging
import uuid
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from app.config.settings import settings
from app.config.loggings import setup_logging

from app.agents.master_agent import master
from app.agents.product_inquiry_agent import handle_product_inquiry
from app.agents.order_placement_agent import handle_order_placement
from app.agents.master_agent import master
from app.schemas.api_schema import AgentRequest,AgentResponse


from datetime import datetime, timedelta
from app.database.engine import AsyncSessionLocal
from app.database.models import UserSessions
          
from sqlalchemy import text
from app.utils.sessionid_functions import ensure_session



setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)



router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/start_session")
async def start_session():
    
    user_name: str = "Guest User"
    session_id = str(uuid.uuid4())
    await ensure_session(session_id, user_name=user_name)
    return {"session_id": session_id}



@router.post("/master_agent", response_model=AgentResponse,summary="Agentic Order Management System",
             
             description=( "This is the Master Agent which manages the Order Placement Agent. "
                           "This is the Master Agent which manages the Order Cancellation Agent. "
                            "This is the Master Agent which manages the Product Inquiry RAG System"))

async def super_agent(request: AgentRequest):

    try:

        logging.info("Entering the API request")
        
        session_id = request.session_id
        user_input = request.user_input

        # Ensure session exists in DB
        await ensure_session(session_id=session_id, user_name="Guest User")

        # Log
        logging.info(f"Processing the request for the session id - {session_id}")

        # Call master agent
        logging.info("Calling the master Agent Async")
        result = await master(user_input=user_input,
                                               session_id=session_id)

        # Ensure result is in the expected format

        if isinstance(result, dict):

            response = AgentResponse(
                output=result.get("output", str(result)),
                success=result.get("success", True),
                session_id=session_id
            )
        else:
            response = AgentResponse(
                output=str(result),
                success=True,
                session_id=session_id
            )

        logger.info(f"Successfully processed request for session {session_id}")
        return response

    except Exception as e:
        logger.error(f"Unexpected error for session {session_id}: {str(e)}")
        return AgentResponse(
            output=f"Unexpected error: {str(e)}",
            success=False,
            session_id=session_id
        )










