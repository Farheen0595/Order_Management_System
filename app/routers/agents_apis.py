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



logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

@router.get("/start_session")
async def start_session():
    """Start a new session for user interaction."""
    logger.info("Received request to start new session")
    
    user_name: str = "Guest User"
    session_id = str(uuid.uuid4())
    logger.debug(f"Generated new session ID: {session_id}")
    
    try:
        await ensure_session(session_id, user_name=user_name)
        logger.info(f"Session created successfully: {session_id}")
        return {"session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to create session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create session")



@router.post("/master_agent", response_model=AgentResponse,
             summary="Agentic Order Management System",
             description=("This is the Master Agent which manages the Order Placement Agent. "
                        "This is the Master Agent which manages the Order Cancellation Agent. "
                        "This is the Master Agent which manages the Product Inquiry RAG System"))

async def super_agent(request: AgentRequest):
    """Handle master agent requests."""
    session_id = request.session_id
    logger.info(f"Received master agent request - Session: {session_id}")
    logger.debug(f"User input: {request.user_input[:100]}...")  # Log first 100 chars

    try:
        # Ensure session exists in DB
        logger.debug(f"Validating session: {session_id}")
        await ensure_session(session_id=session_id, user_name="Guest User")
        
        # Call master agent
        logger.info("Invoking master agent")
        result = await master(
            user_input=request.user_input,
            session_id=session_id
        )
        logger.debug(f"Master agent raw result: {result}")

        # Process response
        if isinstance(result, dict):
            logger.debug("Processing dictionary response")
            response = AgentResponse(
                output=result.get("output", str(result)),
                success=result.get("success", True),
                session_id=session_id
            )
        else:
            logger.debug("Processing non-dictionary response")
            response = AgentResponse(
                output=str(result),
                success=True,
                session_id=session_id
            )

        logger.info(f"Request processed successfully - Session: {session_id}")
        logger.debug(f"Final response: {response}")
        return response

    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        logger.error(f"Session {session_id}: {error_msg}", exc_info=True)
        return AgentResponse(
            output=f"Unexpected error: {str(e)}",
            success=False,
            session_id=session_id
        )










