# app/agents/order_cancellation_agent.py
import json
import logging
from tenacity import retry, stop_after_attempt, wait_fixed
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
import re
from app.agents.memory import get_by_session_id
from app.config.settings import settings
from app.config.constants import constants
from app.config.loggings import setup_logging
from app.tools.order_cancellation_tools import OrderCancellationTool

# ------------------------------- Setup Logging -------------------------------
# setup_logging(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ------------------------------- Agent Creation -------------------------------
def create_order_cancellation_agent(session_id: str):
    """Create a simple, conversational Order Cancellation Agent."""
    logger.info(f"Creating order cancellation agent for session: {session_id}")

    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model=constants.DEFAULT_MODEL,
        api_key=settings.GEMINI_API_KEY,
        max_tokens=2000,
        temperature=0
    )

    # Connect to database and setup SQL tools
    db_url = f"mysql+pymysql://{settings.DB_USERNAME}:{settings.DB_PASSWORD}@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}"
    try:
        db = SQLDatabase.from_uri(db_url)
        sql_tools = SQLDatabaseToolkit(db=db, llm=llm).get_tools()
        logger.info(f"SQL Toolkit initialized with {len(sql_tools)} tools")
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}", exc_info=True)
        sql_tools = []

    # Initialize cancellation tool
    cancellation_tool = OrderCancellationTool(session_token=session_id)
    tools = sql_tools + [cancellation_tool]
    logger.info(f"Total tools initialized: {len(tools)}")

   # ------------------------------------------------------------------------
    instructions = """
You are an **Order Cancellation Agent**.  
Your job is to help users **verify and cancel orders** safely, politely, and reliably.

---

## ⚙️ Core Responsibilities
1. **Validate Orders** using SQL Toolkit (`sql_db_query_checker` + `sql_db_query`).
2. **Cancel Orders** using the `Order_Cancellation_Tool`.

Always respond in **JSON format** with a single key `"output"`.

---

## 🔍 Order Validation Workflow
- Query the `Orders` table to check if the provided `order_number` exists.
- Example:
  SELECT order_number, sku, quantity, status
  FROM Orders
  WHERE order_number = '<order_number>';

### If user didn’t give order_number:
{{"output": "Please provide your order ID (for example, ORD-1234ABCD) so I can locate your order."}}

### If invalid order_number:
{{"output": "❌ Invalid order ID. Please check and provide a valid order ID."}}

### If valid:
{{"output": "📦 Order found! Order ID: <order_number>, Status: <status>, Item: <sku> × <quantity>. Do you want to cancel this order?"}}

---

## 💬 Confirmation Rules
- If user says **yes** → proceed to cancellation.
- If user says **no** → stop and respond politely:
  {{"output": "🙏 Okay, no cancellation made. Do you need any other assistance?"}}
- Never cancel an order without clear “yes” confirmation.

---

## 🧾 Cancellation Workflow
When confirmed, run:
{{
  "action": "cancel_order",
  "order_number": "<order_number>",
  "reason": "<reason or default>"
}}

### Tool Rules
- `action` = "cancel_order" (always)
- `order_number` = must match validated ID
- `reason` = "Customer cancelled the order" if not given

### Tool Internals
1. Update `Orders` → `status = 'CANCELLED'`
2. Insert record into `OrderAudit`
3. Update `Inventory` → restore cancelled item quantity
4. Insert into `InventoryAudit`
5. Calculate refund (`quantity × price`)
6. Send email via SendGrid to the customer
   - Includes order details, cancelled items, refund info

---

## 💌 Email Handling
- On success:
  {{"output": "✅ Your order (ID: ORD-1234ABCD) has been cancelled. Refund of $199.99 will be processed within 5 working days. 💳 Email sent to: user@example.com."}}
- If email fails:
  {{"output": "✅ Order ORD-1234ABCD cancelled successfully. Refund of $199.99 processed. ⚠️ Email notification failed to send."}}

---

## ⚠️ Error & Fallback Rules
If anything fails (SQL, tool, or logic):
{{"output": "⚠️ Unable to process your cancellation right now. Please try again later."}}

If order already cancelled:
{{"output": "⚠️ Order ORD-1234ABCD is already cancelled."}}

If no order ID even after asking:
{{"output": "⚠️ Unable to proceed without a valid order ID. Please provide your order number."}}

---

## 🧠 Behavior Guidelines
- Always validate before cancelling.
- Always ask for confirmation (“yes”) before cancelling.
- Always reply with JSON → {{"output": "..."}} only.
- Be polite, clear, and human-like.
- Never expose SQL queries, Python traces, or tool outputs.

---

## 💬 Example Conversations
User: "Cancel my order ORD-1234"  
→ Validate → Confirm → Cancel → Send email

User: "Cancel my order"  
→ Ask for order ID

User: "Yes, cancel it"  
→ Run Order_Cancellation_Tool

User: "No"  
→ Stop politely

---

You are a professional and helpful agent.  
Always ensure safe, correct, and user-friendly order cancellations.
"""


    prompt = ChatPromptTemplate.from_messages([
        ("system", instructions),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}")
    ])

    logger.debug("Prompt initialized for OrderCancellationAgent.")

    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
    logger.debug("Tool-calling agent created successfully.")

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=12,
        return_intermediate_steps=True,  # Enable for step-level observation
    )

    agent_with_memory = RunnableWithMessageHistory(
        runnable=executor,
        get_session_history=get_by_session_id,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    logger.info("Combined Order Cancellation Agent created successfully.")
    return agent_with_memory


# ------------------------------------------------------------------------
# Clean JSON output
# ------------------------------------------------------------------------
def clean_json_output(output: str) -> str:
    if not isinstance(output, str):
        output = str(output)
    out = output.strip()
    if out.startswith("```"):
        out = re.sub(r"^```(?:json)?", "", out)
    if out.endswith("```"):
        out = out[:-3].strip()
    return out.strip()


# ------------------------------------------------------------------------
# Main Handler
# ------------------------------------------------------------------------
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def handle_order_cancellation(session_id: str, user_input: str):
    logger.info(f"\n Handling Order Cancellation - Session: {session_id}")
    logger.info(f"User Input: {user_input}")
    logger.info("=" * 80)

    try:
        agent = create_order_cancellation_agent(session_id=session_id)

        logger.debug(" Invoking LLM agent with async execution...")
        result = await agent.ainvoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}}
        )

        logger.info(" Raw Agent Result received.")
        logger.debug(f" Raw result structure: {type(result)}")
        logger.debug(f" Raw Result: {result}")

      
        intermediate_steps = result.get("intermediate_steps", []) if isinstance(result, dict) else []
        if intermediate_steps:
            logger.info(f"🔧 Intermediate Steps Count: {len(intermediate_steps)}")
            for idx, (action, observation) in enumerate(intermediate_steps):
                logger.debug(f" Step {idx + 1}: Action -> {action}")
                logger.debug(f" Step {idx + 1}: Observation -> {observation}")


        output_raw = result.get("output") if isinstance(result, dict) else str(result)
        logger.debug(f" Raw Output: {output_raw}")

        cleaned = clean_json_output(output_raw)
        logger.debug(f" Cleaned Output: {cleaned}")

        try:
            parsed = json.loads(cleaned)
            logger.debug(f" Parsed JSON Output: {parsed}")
        except json.JSONDecodeError:
            logger.warning(" JSON Decode Error. Falling back to string output.")
            parsed = {"output": cleaned or "Unable to process your request right now."}

        if not parsed.get("output"):
            parsed = {"output": "Unable to process your cancellation at this time. Please try again later."}
            logger.warning("  No 'output' key found in parsed JSON, using fallback message.")

        final_response = {
            "output": parsed["output"],
            "success": True,
            "session_id": session_id
        }

        logger.info(" Order Cancellation handled successfully.")
        logger.debug(f" Final Response: {final_response}")
        return final_response

    except Exception as e:
        logger.error(f" Exception in handle_order_cancellation: {str(e)}", exc_info=True)
        return {
            "output": "Something went wrong while processing your cancellation. Please try again later.",
            "success": False,
            "session_id": session_id
        }
