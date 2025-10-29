import json
import logging
from sqlalchemy import select
from app.database.models import Inventory
from app.database.engine import AsyncSessionLocal
from app.config.loggings import setup_logging
from app.config.constants import constants
from app.config.settings import settings
from app.agents.memory import get_by_session_id
from app.rag_services.vector_retrieval import VectorRetriever
from langchain_core.messages import HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# -------------------------------------------------------------
# Setup Logging
# -------------------------------------------------------------
# setup_logging(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class RAGRunner:
    """Retrieval-Augmented Generation (RAG) workflow runner."""

    def __init__(self):
        logger.debug("Initializing RAGRunner...")
        self.vector_retriever = VectorRetriever()
        self.collection = constants.COLLECTION_NAME
        logger.info(f"RAGRunner initialized with collection: {self.collection}")

    # -------------------------------------------------------------
    # Intent Detection
    # -------------------------------------------------------------
    async def detect_intent(self, user_query: str) -> str:
        """Use LLM to classify user intent between 'products' and 'product_details'."""
        logger.debug(f"Detecting intent for query: {user_query}")

        system_prompt = """
        You are an intent classifier for a product inquiry assistant.
        Classify the user query into one of these intents:
        - products → if user wants to see available products, best, or list of products.
        - product_details → if user asks about a specific product or more details.

        Respond ONLY with one of these two words: 'products' or 'product_details'.
        """

        llm = ChatGoogleGenerativeAI(
            model=constants.DEFAULT_MODEL,
            api_key=settings.GEMINI_API_KEY,
            temperature=0,
            max_tokens=100
        )

        try:
            response = await llm.ainvoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ])

            intent = response.content.strip().lower()
            if intent not in ["products", "product_details"]:
                logger.warning(f"Invalid intent '{intent}', defaulting to 'products'")
                intent = "products"

            logger.info(f"Detected intent: {intent}")
            return intent

        except Exception as e:
            logger.error(f"Intent detection failed: {str(e)}", exc_info=True)
            return "products"

    # -------------------------------------------------------------
    # Fetch Top Products
    # -------------------------------------------------------------
    async def get_products(self, limit: int = 5):
        """Fetch top products by quantity available from DB."""
        logger.debug(f"Fetching top {limit} products from DB")

        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Inventory.product_name)
                    .order_by(Inventory.quantity_available.desc())
                    .limit(limit)
                )
                product_names = result.scalars().all()

            logger.info(f"Retrieved {len(product_names)} products: {product_names}")
            return product_names

        except Exception as e:
            logger.error(f"Failed to fetch products: {str(e)}", exc_info=True)
            return []

    # -------------------------------------------------------------
    # Main RAG Execution
    # -------------------------------------------------------------
    async def run(self, session_id: str, user_input: str):
        logger.info(f"Running RAG process | Session: {session_id}")
        logger.debug(f"User Input: {user_input}")

        memory = get_by_session_id(session_id)
        intent = await self.detect_intent(user_input)

        try:
            # ------------------ Step 1: Retrieve Context ------------------
            if intent == "products":
                logger.debug("Intent: 'products' → Retrieving product list")
                product_names = await self.get_products()

                vec_json = await self.vector_retriever.fetch_by_product_names(
                    collection_name=self.collection,
                    product_names=product_names
                )

            else:
                logger.debug("Intent: 'product_details' → Searching for product details")
                vec_json = await self.vector_retriever.search(
                    collection_name=self.collection,
                    query=user_input,
                    k=1
                )

            context_docs = json.loads(vec_json).get("output", [])
            logger.debug(f"Retrieved {len(context_docs)} documents from vector store")

            # ------------------ Step 2: Build Context String ------------------
            if not context_docs:
                human_context_str = "No relevant products found."
            else:
                human_context = []
                for item in context_docs:
                    entry = (
                        f"Product: {item.get('title', 'N/A')}\n"
                        f"Brand: {item.get('brand', 'N/A')}\n"
                        f"Price: {item.get('price', 'N/A')}\n"
                        f"Details: {item.get('content', '')}\n"
                    )
                    human_context.append(entry)
                human_context_str = "\n".join(human_context)

            # ------------------ Step 3: System Prompt ------------------
            system_prompt = f"""
            You are a helpful Product Inquiry Assistant.

            Behavior Rules:
            - If intent is 'products', show a list of available products with brand, price, and 1-line summary.

                Example Format:
                ✨ *Available Products:*
                1. **Men's Running Shoes** by Nike – $89.99  
                2. **Data Science Handbook** by O'Reilly – $59.99  
                3. **Wireless Bluetooth Headphones** by Sony – $199.99  

            - If intent is 'product_details', show detailed product specs and highlights.
            - Use bullet points and short sentences.
            - Never hallucinate. Use only provided context.
            - If nothing relevant, say: "Sorry, I couldn’t find that information."

            Intent: {intent}
            Context:
            {human_context_str}
            """

            # ------------------ Step 4: Build Chat History ------------------
            messages = [{"role": "system", "content": system_prompt}]
            for m in memory.messages:
                if isinstance(m, HumanMessage):
                    messages.append({"role": "user", "content": m.content})
                elif isinstance(m, AIMessage):
                    messages.append({"role": "assistant", "content": m.content})
            messages.append({"role": "user", "content": user_input})

            # ------------------ Step 5: Generate Response ------------------
            llm = ChatGoogleGenerativeAI(
                model=constants.DEFAULT_MODEL,
                api_key=settings.GEMINI_API_KEY,
                temperature=0.3,
                max_tokens=2000,
                request_timeout=60
            )

            logger.debug("Invoking LLM for response generation")
            response = await llm.ainvoke(messages)
            answer = response.content.strip()

            # ------------------ Step 6: Save to Memory ------------------
            memory.add_messages([
                HumanMessage(content=user_input),
                AIMessage(content=answer)
            ])
            logger.debug("Conversation updated in memory")

            logger.info(f"RAG process completed successfully for session {session_id}")

            return {"success": True, "session_id": session_id, "output": answer}

        except Exception as e:
            logger.error(f"RAG pipeline failed: {str(e)}", exc_info=True)
            return {"success": False, "session_id": session_id, "output": f"Error: {str(e)}"}


# -------------------------------------------------------------
# Helper Function
# -------------------------------------------------------------
async def handle_product_inquiry(session_id: str, user_input: str):
    """Entry point to handle product queries asynchronously."""
    logger.info(f"Handling product inquiry for session {session_id}")
    agent = RAGRunner()
    result = await agent.run(session_id=session_id, user_input=user_input)
    logger.info(f"Completed product inquiry for session {session_id}")
    return result
