from langchain_core.messages import BaseMessage
from langchain_core.chat_history import BaseChatMessageHistory
from pydantic import BaseModel, Field
import logging

# Setup logging
logger = logging.getLogger(__name__)

class InMemoryHistory(BaseChatMessageHistory, BaseModel):
    """In memory implementation of chat message history."""

    messages: list[BaseMessage] = Field(default_factory=list)

    def add_messages(self, messages: list[BaseMessage]) -> None:
        """Add a list of messages to the store"""
        logger.debug(f"Adding {len(messages)} messages to history")
        self.messages.extend(messages)
        logger.debug(f"History size now: {len(self.messages)} messages")

    def clear(self) -> None:
        logger.info("Clearing message history")
        self.messages = []
        logger.debug("Message history cleared")

# Here we use a global variable to store the chat message history.
# This will make it easier to inspect it to see the underlying results.
store = {}

def get_by_session_id(session_id: str) -> BaseChatMessageHistory:
    logger.debug(f"Retrieving chat history for session: {session_id}")
    if session_id not in store:
        logger.info(f"Creating new history for session: {session_id}")
        store[session_id] = InMemoryHistory()
    else:
        logger.debug(f"Found existing history for session: {session_id}")
    return store[session_id]