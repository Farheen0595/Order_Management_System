# app/rag_services/rag_runner.py

import logging
import json
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from app.agents.memory import get_by_session_id
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config.settings import settings
from app.config.loggings import setup_logging
from app.rag_services.vector_retrieval import VectorRetriever

logger = logging.getLogger(__name__)


class RAGRunner:
    """
    General RAG pipeline:
    - Maintains session memory
    - Retrieves context
    - Prepares messages
    - Calls provider LLM
    - Saves history
    """

    def __init__(self):

        self.query = VectorRetriever().search

    async def run(self,
                    session_id: str,
                    query: str,
                    collection: str = settings.COLLECTION_NAME,
                    k: int = settings.DEFAULT_TOP_K
                    ) -> Dict[str, Any]:

                    
        memory = get_by_session_id(session_id)


        logger.info("SESSION ID=%s", session_id)
        logger.debug("Existing Memory=%s", memory.messages)


        raw_context = await self.query(collection, query, k)
        print(f"printing the context {raw_context}")

        context = json.loads(raw_context)

        if not context.get("success", False):
            return {
                    "output": " The answer is not in the provided documents.",
                    "success": False,
                    "session_id": session_id,}

        logger.debug("Retrieved Context=%s", context)

        llm_messages = []
        for m in memory.messages:
            if isinstance(m, HumanMessage):
                llm_messages.append({"role": "user", "content": m.content})
            elif isinstance(m, AIMessage):
                llm_messages.append({"role": "assistant", "content": m.content})

        messages = [
                    {
                    "role": "system",
                        "content": (
                            "You are a precise assistant grounded strictly in the provided context. "
                            "If the answer is not in the context, reply exactly: "
                            "\"The answer is not in the provided documents.\""
                        ),},
            {"role": "system", "content": f"Retrieved context:\n{context['output']}"},]
        
        messages.extend(llm_messages)
        messages.append({"role": "user", "content": query})

        llm = ChatGoogleGenerativeAI(
            model=settings.DEFAULT_MODEL,
            api_key=settings.GEMINI_API_KEY,
            max_tokens=2000,
            temperature=0,
            request_timeout=60,
        )



        try:
            response = await llm.ainvoke(messages)   
            final_answer = response.content.strip() 
            print("Final answer:", final_answer)

        except Exception as e:
            logger.exception("LLM call failed for model=%s", settings.DEFAULT_MODEL)
            return {
                "output": f"Error calling LLM: {str(e)}",
                "success": False,
                "session_id": session_id,
            }

        # Save new turn into memory
        memory.add_messages([
            HumanMessage(content=query),
            AIMessage(content=final_answer),  
        ])

        return {
            "output": final_answer,
            "success": True,
            "session_id": session_id,
            "context_used": context,
        }



async def handle_product_inquiry(session_id: str,
                                user_input: str):
    agent = RAGRunner()
    return await agent.run(session_id=session_id, 
                           query=user_input)
