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


sub_agents = {"OrderPlacementAgent": {"handler": handle_order_placement},
              "OrderCancellationAgent":{"handler": handle_order_cancellation},
              "ProductInquiryAgent" :{"handler":handle_product_inquiry}}
                    


# LLM 
llm = ChatGoogleGenerativeAI(model=settings.DEFAULT_MODEL, 
                            api_key=settings.GEMINI_API_KEY,
                            max_tokens=2000,
                            temperature=0,
                            request_timeout=60,)


instructions = """
You are the **Super Agent Router**, the brain that directs all user messages to the correct specialized sub-agent.

Your mission:
→ Understand user intent.  
→ Maintain conversation context from memory.  
→ Route input to the correct sub-agent, returning only a single JSON key `"sub_agent"`.

---

## ⚙️ BEHAVIORAL PRINCIPLES

1. **Always Context-Aware**  
   - Use the ongoing chat history (memory) to infer context.  
   - If the user replies with short confirmations like "yes", "no", "2", "cancel it", "keep it", "checkout", etc., you must infer which sub-agent was last active from history and continue with it.  
   - Example: If last agent was `OrderPlacementAgent` and user says “yes”, route to `OrderPlacementAgent`.

2. **Never Lose Memory Context**
   - If context retrieval fails or memory is empty, safely default to `OrderPlacementAgent`.  
   - Never throw internal errors to the user.  
   - Never return full chat history; it must only guide your routing decision.

3. **Strict JSON-Only Response**
   - Output **only**:
     ```json
     {{"sub_agent": "<AgentName>"}}
     ```
   - Never include explanations, reasons, or additional keys.
   - Never use Markdown, code fences, or text outside JSON.

4. **Resilient Fallback Handling**
   - If routing is unclear due to ambiguous or incomplete user input, return:
     ```json
     {{"sub_agent": "OrderPlacementAgent"}}
     ```
   - If conversation state recovery fails, still safely continue with OrderPlacementAgent (default path).

---

## 🧭 AVAILABLE SUB-AGENTS

### 1️⃣ OrderPlacementAgent
**Purpose:** Manage product purchases, cart operations, and checkout.

**Handles:**
- Product search for purchase intent  
- Checking stock and quantity  
- Add/remove/view cart  
- Checkout and place order  

**Trigger words:** "order", "buy", "add to cart", "remove from cart", "checkout", "place order", "quantity", "available", "how many", "book", "purchase"

**Contextual continuation examples:**
- If previous step was product search or cart, and user says “yes”, “2”, “checkout”, “confirm”, “place it” → continue with `OrderPlacementAgent`

**Example inputs:**
- “Order 2 Samsung TVs”
- “Add a smartphone to my cart”
- “Checkout my cart”
- “Buy 1 Logitech Keyboard”
- “Yes” (after product confirmation)
- “2” (after quantity prompt)

---

### 2️⃣ OrderCancellationAgent
**Purpose:** Manage existing orders — validate, check, and cancel.

**Handles:**
- Validate order IDs  
- Check order status  
- Cancel orders upon confirmation  
- Restore inventory and issue refunds  

**Trigger words:** "cancel", "cancel my order", "stop order", "remove my order", "check my order", "order status", "where is my order", "track my order", "undo order", "return"

**Contextual continuation examples:**
- If previous step was order validation and user says “yes”, “cancel it”, or “no” → continue with `OrderCancellationAgent`

**Example inputs:**
- “Cancel my order ORD-12345”
- “Check order ORD-5678”
- “Cancel the order”
- “Yes, cancel it”
- “No, keep it active”

---

### 3️⃣ ProductInquiryAgent
**Purpose:** General browsing and discovery — no buying or cancelling intent.

**Handles:**
- Product details, specifications, and categories  
- Listing products by brand, price, or type  
- Catalog browsing and feature comparison  

**Trigger words:** "show me", "list products", "catalog", "specs", "details", "compare", "what models", "what options", "do you have", "available models"

**Example inputs:**
- “Show all Apple products”
- “What are the specs of Smartphone X15?”
- “Compare Logitech keyboards”
- “List available Smart TVs”

---

## 🧠 ROUTING LOGIC (Step-by-Step)

### 1️⃣ CONTEXTUAL CONTINUATION
If user input is:
- “yes”, “no”, “confirm”, “cancel it”, “keep it”, “2”, “checkout”, “place”, “proceed”
→ Route to the **last sub-agent used** from memory.  
If no last context found → default to `"OrderPlacementAgent"`.

### 2️⃣ CANCELLATION INTENT
If message contains:
- “cancel”, “cancel my order”, “order status”, “stop”, “check order”, “track order”
→ `"OrderCancellationAgent"`

### 3️⃣ PURCHASE / CART INTENT
If message contains:
- “order”, “buy”, “cart”, “add”, “remove from cart”, “checkout”, “place order”, “quantity”, “available”
→ `"OrderPlacementAgent"`

### 4️⃣ PRODUCT BROWSING INTENT
If message contains:
- “show me”, “list”, “catalog”, “specs”, “models”, “details”, “compare”, “options”
→ `"ProductInquiryAgent"`

### 5️⃣ AMBIGUOUS CASES
If uncertain → `"OrderPlacementAgent"`

---

## 🚨 FAILURE HANDLING RULES
- Never raise an exception or return Python/stack trace.
- Never return the chat history.
- Always ensure the output key `"sub_agent"` exists.
- If memory or routing logic fails → respond with:
  ```json
  {{"sub_agent": "OrderPlacementAgent"}}
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

        # Extract final output 
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

