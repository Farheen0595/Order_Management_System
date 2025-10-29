import json
import logging
import ast
import traceback
from tenacity import retry, stop_after_attempt, wait_fixed
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from app.config.settings import settings
from app.config.constants import constants
from app.agents.memory import get_by_session_id
from app.agents.order_placement_agent import handle_order_placement
from app.agents.order_cancellation_agent import handle_order_cancellation
from app.agents.product_inquiry_agent import handle_product_inquiry
from app.config.loggings import setup_logging

# Setup logging
logger = logging.getLogger(__name__)

# Sub-agent registry
sub_agents = {
                "OrderPlacementAgent": {"handler": handle_order_placement},
                "OrderCancellationAgent": {"handler": handle_order_cancellation},
                "ProductInquiryAgent": {"handler": handle_product_inquiry},
            }

# LLM setup
llm = ChatGoogleGenerativeAI(
                            model=constants.DEFAULT_MODEL,
                            api_key=settings.GEMINI_API_KEY,
                            max_tokens=1000,
                            temperature=0,
                            request_timeout=60,
)


# Super agent instruction 
instructions = """
You are the **Super Agent Router**, responsible for routing user messages to the correct sub-agent.

Your **only** task:
→ Understand user intent from the message and memory context.  
→ Route to the correct sub-agent.  
→ Respond **only** with a JSON object of the form:
   {{"sub_agent": "<AgentName>"}}

---

## ⚙️ ROUTING PRINCIPLES

1. **Context-Aware**
   - Use conversation memory to infer intent.
   - If the user replies briefly ("yes", "no", "2", "checkout", "cancel", etc.), continue with the last active sub-agent.
   - Example: If the last sub-agent was `OrderPlacementAgent` and user says “yes”, route again to `OrderPlacementAgent`.

2. **Fail-Safe Default**
   - If memory is empty, unclear, or context retrieval fails → use `OrderPlacementAgent`.

3. **Strict Output Format**
   - Respond only with valid JSON:
     {{"sub_agent": "<AgentName>"}}
   - No Markdown, no explanations, no extra words.

4. **Unrecognized Input**
   - Default to {{"sub_agent": "OrderPlacementAgent"}}.

---

## 🧭 AVAILABLE SUB-AGENTS

### 1️⃣ OrderPlacementAgent
Handles ordering, buying, cart updates, checkout.
Trigger words: "order", "buy", "add to cart", "remove", "checkout", "place order", "quantity", "available", "book", "purchase".
Continuation triggers: "yes add 2", "2 units ", "confirm", "checkout".

### 2️⃣ ProductInquiryAgent
Handles product browsing, details, and specifications.
Trigger words: "show me", "list products", "catalog", "specs", "details", "models", "options", "available".

### 3️⃣ OrderCancellationAgent
Handles order cancellations, refunds, and returns.
Trigger words: "cancel", "refund", "return", "void order", "abort order", "cancel order", "order cancellation".
Continuation triggers: "cancel", "refund", "abort".

---

## 🧩 WORKFLOW SUMMARY

1. Use context + trigger words to pick the correct sub-agent.
2. If continuation message → reuse last active sub-agent.
3. Always output strict JSON:
   {{"sub_agent": "<AgentName>"}}
4. Do **not** include explanations, Markdown, or other text.
5. Do **not** generate tool responses or "output" text — only route.

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
                                        output_messages_key="output",)


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
        logger.info(f"[SUPER AGENT] Processing input='{user_input}' | session_id={session_id}")

        # Invoke master agent
        resp = await master_agent.ainvoke({"input": user_input},config={"configurable": {"session_id": session_id}})
        
        logger.debug(f"[SUPER AGENT] LLM response: {resp.content}")

        data = extract_json(resp.content)
        logger.debug(f"[SUPER AGENT] Parsed {data}")

        if not data:

            logger.error(f"[SUPER AGENT]] Failed to extract JSON from LLM response: {resp.content}")

            return {"success": False, "error": "Failed to extract JSON", "raw": resp.content}
        
        sub_agent_name = data.get("sub_agent")
        logger.info(f"[SUPER AGENT] Selected sub-agent: {sub_agent_name}")

        agent_entry = sub_agents.get(sub_agent_name)

        if not agent_entry:
            logger.error(f"[SUPER AGENT] Unsupported sub-agent: {sub_agent_name}")
            return {"success": False, "error": f"Unsupported sub-agent: {sub_agent_name}", "raw": data}



        # Call the selected sub-agent
        try:
            sub_result = await agent_entry["handler"](session_id,user_input=user_input)
            logger.debug(f"[SUPER AGENT] RAW sub-agent result: {sub_result}")

        except Exception as e:
            logger.exception(f"[SUPER AGENT] Error in sub-agent '{sub_agent_name}'")
            return {"output": f"Error in {sub_agent_name}: {str(e)}",
                    "success": False,
                    "session_id": session_id}
        
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
                "session_id": sub_result.get("session_id", session_id)}

    except Exception as e:

        logger.exception("[SUPER AGENT] Unexpected error")
        return {
                "output": f"Unexpected error in master agent: {str(e)}",
                "success": False,
                "session_id": session_id}