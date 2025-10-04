import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from tenacity import retry, stop_after_attempt, wait_fixed
import ast
import traceback
from app.config.settings import settings
from app.agents.memory import get_by_session_id
from app.agents.order_placement_agent import handle_order_placement
from app.agents.order_cancellation_agent import handle_order_cancellation
from app.agents.product_inquiry_agent import handle_product_inquiry


import logging
from app.config.loggings import setup_logging

setup_logging(level=logging.DEBUG)
logger = logging.getLogger(__file__)


sub_agents = {
                "OrderPlacementAgent": {"handler": handle_order_placement},

                "OrderCancellationAgent" :{"handler": handle_order_cancellation} ,
                "ProductInquiryAgent" :{"handler":handle_product_inquiry}
            }
                    

# LLM 
llm = ChatGoogleGenerativeAI( model=settings.DEFAULT_MODEL, api_key=settings.GEMINI_API_KEY,
                                max_tokens=2000,
                                temperature=0,
                                request_timeout=60,)



instructions = """
You are the Super Agent.  

Your ONLY job is to understand the intent of the user query and route it to the correct sub-agent.  

⚠️ STRICT RULES:
- Always output a valid JSON object with a single key `"sub_agent"`.  
- Never include `"output"` in your response.  
- Never generate explanations, SQL, or text. Only return JSON.  
- Do NOT re-emit or modify the sub-agent’s outputs (e.g., confirmations, cancellations, product answers). That is handled entirely by the sub-agents.  

---

### Available Sub-Agents

1. OrderPlacementAgent  
   - Handles everything related to **new orders and cart management**.  
   - Scope:  
     - Product search in inventory  
     - Add to cart / remove from cart  
     - View cart contents  
     - Checkout and place orders  
   - Example queries:  
     - "Order 2 Wireless Bluetooth Headphones"  
     - "Add 1 Apple Smartphone X15 to my cart"  
     - "Show my cart"  
     - "Checkout my cart"  
     - "Place this order"  

2. OrderCancellationAgent  
   - Handles everything related to **checking and cancelling existing orders**.  
   - Scope:  
     - Validate order IDs in database  
     - Ask for confirmation before cancellation  
     - Cancel order if confirmed  
   - Example queries:  
     - "Cancel my order ORD-12345"  
     - "Check order number 12345"  
     - "Yes, cancel my order"  
     - "No, keep my order"  

3. ProductInquiryAgent  
   - Handles everything related to **general product questions and catalog exploration**.  
   - Scope:  
     - Brand-level or category-level product queries  
     - Feature questions not tied to specific cart actions  
     - Uses FAISS/cosine similarity search for catalogs  
   - Example queries:  
     - "Show me Home Appliances"  
     - "Does Apple Smartphone X15 exist?"  
     - "List all Bluetooth headphones"  
     - "What Samsung TVs do you have?"  

---

### Routing Logic
- If the query is about **buying, adding to cart, or checkout** → route to `OrderPlacementAgent`.  
- If the query is about **cancelling or checking an existing order** → route to `OrderCancellationAgent`.  
- If the query is about **exploring or asking about products without ordering/cancelling** → route to `ProductInquiryAgent`.  
- If unsure, prefer **OrderPlacementAgent** (because most ambiguous queries involve new purchases).  

---

### Final Rule
Your output format is **always exactly**:

{{
  "sub_agent": "<AgentName>"
}}

⚠️ Never return more than one sub-agent.  
⚠️ Never return free text.  
⚠️ Never include `"output"` here.  
"""




# Prompt template
prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(instructions),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])


chain = prompt | llm


# Runnable with history
master_agent = RunnableWithMessageHistory(
    runnable=chain,
    get_session_history=get_by_session_id,
    input_messages_key="input",
    history_messages_key="chat_history",
    output_messages_key="output",
)


# JSON extraction 
def extract_json(text: str):

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError as e:
            print("JSON decode failed:", e)
    return None




@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def master(user_input: str, session_id: str):
    try:
        logger.info(f"[MASTER_AGENT] Processing input='{user_input}' | session_id={session_id}")

        # Run classification through master agent
        resp = await master_agent.ainvoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}}
        )
        logger.debug(f"[MASTER_AGENT] Raw LLM response: {resp.content}")

        data = extract_json(resp.content)
        logger.debug(f"[MASTER_AGENT] Parsed {data}")

        if not data:
            logger.error(f"[MASTER_AGENT] Failed to extract JSON from LLM response: {resp.content}")
            return {"ok": False, "error": "Failed to extract JSON", "raw": resp.content}

        # If LLM already returned a sub-agent response (contains "output")
        if "output" in data and "sub_agent" not in data:
            logger.info("[MASTER_AGENT] Detected direct sub-agent output, forwarding to user")
            return {
                "output": data["output"],
                "success": True,
                "session_id": session_id
            }

        # Normal flow → route to sub-agent
        sub_agent_name = data.get("sub_agent")
        logger.info(f"[MASTER_AGENT] Selected sub-agent: {sub_agent_name}")

        agent_entry = sub_agents.get(sub_agent_name)
        if not agent_entry:
            logger.error(f"[MASTER_AGENT] Unsupported sub-agent: {sub_agent_name}")
            return {"ok": False, "error": f"Unsupported sub-agent: {sub_agent_name}", "raw": data}

        try:
            sub_result = await agent_entry["handler"](session_id, user_input=user_input)
            logger.debug(f"[MASTER_AGENT] Raw sub-agent result: {sub_result}")
        except Exception as e:
            logger.exception(f"[MASTER_AGENT] Error in sub-agent '{sub_agent_name}'")
            return {
                "output": f"Error in {sub_agent_name}: {str(e)}",
                "success": False,
                "session_id": session_id
            }

        # Extract final output safely
        output_val = sub_result.get("output", "")
        if isinstance(output_val, str):
            try:
                nested = ast.literal_eval(output_val)
                output_val = nested.get("output", output_val)
            except Exception:
                pass

        return {
            "output": output_val,
            "success": sub_result.get("success", False),
            "session_id": sub_result.get("session_id", session_id)
        }

    except Exception as e:
        logger.exception("[MASTER_AGENT] Unexpected error")
        return {
            "output": f"Unexpected error in master agent: {str(e)}",
            "success": False,
            "session_id": session_id
        }

