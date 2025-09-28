import logging
from typing import Optional
import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from app.config.settings import settings
from app.config.loggings import setup_logging
import uuid

from app.agents.master_agent import master
from app.agents.order_cancellation_agent import handle_order_cancellation
from app.agents.order_placement_agent import handle_order_placement
from app.schemas.api_schema import AgentRequest,AgentResponse


setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/master_agent", response_model=AgentResponse,summary="Agentic Order Management System",
             
             description=( "This is the Master Agent which manages the Order Placement Agent. "
                           "This is the Master Agent which manages the Order Cancellation Agent. "
                            "This is the Master Agent which manages the Product Enqiry RAG System"))


async def super_agent(request : AgentRequest):

    """
    Process user input through the master agent system.
    
    - **session_id**: Unique identifier for the conversation session
    - **user_input**: The message or query from the user
    """

    try:
        print("Enter into the api request call")
        session_id = request.session_id
        user_input = request.user_input


        # log the request 

        logging.info(f"Processing the request for the session id - {session_id}")


        # calling the master agent
        logging.info("Calling the master Agent Async")
        result =  await master(user_input=user_input,
                            session_id=session_id)
        


        # Ensure result is in the expected format
        if isinstance(result, dict):
            response = AgentResponse(
                output=result.get("output",str(result)),
                success=result.get("success",True),
                session_id=session_id)
        else:
            response = AgentResponse(
                output=result.get("output",str(result)),
                success=result.get("success",True),
                session_id=session_id)
            

        logger.info(f"Successfully processed request for session {request.session_id}")
        return response

    except Exception as e:
        logger.error(f"Unexpected error for session {session_id}: {str(e)}")

        return AgentResponse(
            output=f" Unexpected error: {str(e)}",
            success=False,
            session_id=request.session_id)

          

    








