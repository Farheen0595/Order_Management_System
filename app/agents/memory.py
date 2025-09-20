from langchain_core.messages import BaseMessage
from langchain_core.chat_history import BaseChatMessageHistory
from pydantic import BaseModel, Field




class InMemoryHistory(BaseChatMessageHistory, BaseModel):
    """In memory implementation of chat message history."""

    messages: list[BaseMessage] = Field(default_factory=list)

    def add_messages(self, messages: list[BaseMessage]) -> None:
        """Add a list of messages to the store"""
        self.messages.extend(messages)

    def clear(self) -> None:
        self.messages = []



# Here we use a global variable to store the chat message history.
# This will make it easier to inspect it to see the underlying results.


store = {}

def get_by_session_id(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryHistory()
    return store[session_id]