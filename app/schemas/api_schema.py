from pydantic import BaseModel,Field
from app.config.loggings import setup_logging
import logging



class AgentRequest(BaseModel):
 
    user_input: str
    session_id: str



class AgentResponse(BaseModel):

    output: str
    success: bool
    session_id : str
    

