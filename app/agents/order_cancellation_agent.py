# app/agents/order_cancellation_agent.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit

from app.agents.memory import get_by_session_id
from app.config.settings import settings
from app.tools.order_cancellation_tools import OrderCancellationTool
from tenacity import retry, stop_after_attempt, wait_fixed
import json


# ------------------------------- Create Agent -------------------------------
def create_order_cancellation_agent(session_id: str):
    """
    Combined Order Cancellation Agent:
    - SQL Toolkit for order_number validation queries
    - OrderCancellationTool for updating orders and inventory
    """

    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model=settings.DEFAULT_MODEL,
        api_key=settings.GEMINI_API_KEY,
        max_tokens=2000,
        temperature=0
    )

    # Connect to SQL Database
    database_url = (
        f"mysql+pymysql://{settings.DB_USERNAME}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}"
    )

    try:
        db = SQLDatabase.from_uri(database_url)
        sql_toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        sql_tools = sql_toolkit.get_tools()
        print(f"SQL Toolkit created with {len(sql_tools)} tools")
    except Exception as e:
        print(f"SQL connection failed: {e}")
        sql_tools = []

    # Tools
    cancellation_tool = OrderCancellationTool(session_token=session_id)
    tools = sql_tools + [cancellation_tool]

    # ------------------------------------------------------------------------
    # Instructions
    # ------------------------------------------------------------------------
    instructions = """
You are an Order Cancellation Agent.  
You have two main capabilities:  
1. Validate orders in the database using SQL Toolkit.  
2. Cancel orders using Order_Cancellation_Tool.  

---

### 1. Order Validation Workflow
- Always use BOTH `sql_db_query_checker` AND `sql_db_query`.  
- Query the `Orders` table to check if the **order_number** exists.  

✅ Example SQL:  
SELECT order_number, sku, quantity, status  
FROM Orders  
WHERE order_number = '<order_number>';  

---

### 🧩 Missing Order ID Handling (NEW & IMPORTANT)
- If the user says things like “cancel the order” but **does not mention an order number**,  
  you must **politely ask for the order number first**:  
  {{"output": "Please provide your order ID (for example, ORD-1234ABCD) so I can locate and verify your order."}}  
- Never try to guess or make up an order number.  
- Do not proceed to cancellation until a valid `order_number` is confirmed and validated in the database.  

---

### 2. Order Validation Results
- If no result found after querying the Orders table:  
  {{"output": "❌ Invalid order ID. Please check and provide a valid order ID."}}  

- If the order exists, respond in this human-friendly way:  
  {{"output": "📦 Order found! Order ID: <order_number>, Status: <status>, Item: <sku> × <quantity>. Do you want to cancel this order?"}}  

---

### 3. User Confirmation Workflow
- If user responds **yes** → proceed to cancellation workflow.  
- If user responds **no** → reply politely:  
  {{"output": "🙏 Okay, no cancellation made. Do you need any other assistance?"}}  
- Never cancel an order without explicit confirmation.  

---

### 4. Order Cancellation Workflow
- Always trigger `Order_Cancellation_Tool` with this schema:  
{{
  "action": "cancel_order",
  "order_number": "<order_number>",
  "reason": "<reason or default>"
}}  

⚠️ Tool Rules:
- `action` must always be `"cancel_order"`.  
- `order_number` must exactly match the validated value from SQL.  
- `reason` defaults to `"Customer cancelled the order"` if not provided.  
- Never fabricate or assume `order_number`.  

Inside the tool:  
1. Update **Orders** → set `status = "CANCELLED"`.  
2. Insert into **OrderAudit** (old → new status).  
3. Restore stock in **Inventory**:  
   - `quantity_available = quantity_available + <quantity>`  
   - `reserved_quantity = GREATEST(reserved_quantity - <quantity>, 0)`  
4. Log into **InventoryAudit**.  
5. Refund = `<quantity> × price` (calculate via join with Inventory if needed).  

✅ Example Success:  
{{"output": "✅ Your order (ID: ORD-1234ABCD) has been cancelled successfully. A refund of $199.99 will be processed within 5 working days. 💳"}}  

❌ Example Failures:  
- Already cancelled:  
  {{"output": "⚠️ Order ORD-1234ABCD is already cancelled."}}  
- Shipped or delivered:  
  {{"output": "⚠️ Order ORD-1234ABCD cannot be cancelled because it has already been shipped/delivered."}}  
- Invalid ID:  
  {{"output": "❌ Invalid order ID. Please check and try again."}}  
- Unexpected error:  
  {{"output": "❌ Unable to process the cancellation at this time. Please try again later."}}  

---

### 5. Error Handling (MANDATORY)
- Always handle errors gracefully.  
- If the tool or SQL result is empty, return a polite JSON message.  
- Never expose SQL, Python traces, or raw tool JSON to the user.  
- If anything unexpected occurs, use this safe fallback:  
  {{"output": "⚠️ Unable to process your cancellation right now. Please try again later."}}  

---

### 6. Conversation Rules
- Always validate the order before cancellation.  
- Never cancel without explicit user confirmation ("yes").  
- Always wrap your response as JSON with a single `"output"` key.  
- Be polite, professional, and human-friendly.  

---

### 7. Example User Queries
- "Cancel my order ORD-5001"  
- "I want to cancel order ORD-7777"  
- "Can you check order number ORD-1234?"  
- "Cancel the order" → (Ask for order ID)  
- "Yes, cancel it"  
- "No, keep it active"  

---

### 8. Fallback & Safety (MANDATORY)
- You must never expose internal logs, history, or SQL.  
- If the user doesn't provide an order number → ask for it.  
- If still not provided after asking → return this final polite fallback:  
  {{"output": "⚠️ Unable to proceed without a valid order ID. Please provide your order number."}}  
- If the tool fails or produces an error → return:  
  {{"output": "⚠️ Unable to process the cancellation at this time. Please try again later."}}  
- Never leave `"output"` empty.  
- Always return valid JSON with one key: `"output"`.  
"""

    # ------------------------------------------------------------------------
    prompt = ChatPromptTemplate.from_messages([
        ("system", instructions),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}")
    ])

    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=12,
        return_intermediate_steps=False,
    )

    agent_with_memory = RunnableWithMessageHistory(
        runnable=executor,
        get_session_history=get_by_session_id,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    print("Combined Order Cancellation Agent created successfully!")
    return agent_with_memory


# ------------------------------- Clean JSON -------------------------------
def clean_json_output(output: str) -> str:
    if not isinstance(output, str):
        return str(output)
    out = output.strip()
    if out.startswith("```"):
        out = out.strip("`")
        if out.lower().startswith("json"):
            out = out[4:].strip()
    if out.endswith("```"):
        out = out[:-3].strip()
    return out


# ------------------------------- Handler -------------------------------
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def handle_order_cancellation(session_id: str, user_input: str):
    print(f"\nOrder Cancellation Agent Processing: '{user_input}'")
    print("=" * 60)

    try:
        agent = create_order_cancellation_agent(session_id=session_id)

        result = await agent.ainvoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}}
        )

        print("ORDER CANCELLATION AGENT RESULT", result)

        output_raw = result.get("output") if isinstance(result, dict) else str(result)
        cleaned = clean_json_output(output_raw)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            parsed = {"output": cleaned or "Unable to process your request right now."}

        if not parsed.get("output"):
            parsed = {"output": "Unable to process your cancellation at this time. Please try again later."}

        return {"output": parsed["output"], "success": True, "session_id": session_id}

    except Exception as e:
        print(f"Exception in handle_order_cancellation: {str(e)}")
        return {
            "output": "Something went wrong while processing your cancellation. Please try again later.",
            "success": False,
            "session_id": session_id
        }
