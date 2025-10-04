# order_cancellation_agent.py
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
from ast import literal_eval


def create_order_cancellation_agent():

    """
    Combined Order Cancellation Agent:
    - SQL Toolkit for order_number check queries
    - OrderCancellationTool for updating orders and inventory
    """

    # LLM
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

    custom_tools = [OrderCancellationTool()]
    all_tools = sql_tools + custom_tools


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
SELECT order_number, customer_email, status, total_amount  
FROM Orders  
WHERE order_number = '<order_number>';  

- If no result found:  
  {{ "output": "❌ Invalid order ID. Please provide a valid order ID." }}  

- If order exists, return in this **polite, human-readable format**:  
  {{ "output": "📦 Order found! Order ID: <order_number>, Status: <status>, Total: $<total_amount>. Do you want to cancel this order?" }}  

---

### 2. User Confirmation Workflow
- If user responds **yes** → proceed to cancellation workflow.  
- If user responds **no** → reply politely:  
  {{ "output": "🙏 Okay, no cancellation made. Do you need any other assistance?" }}  
- Do not proceed with cancellation without explicit **yes** from the user.  

---

### 3. Order Cancellation Workflow
- To cancel an order, always trigger `Order_Cancellation_Tool` with this schema:  
{{
  "action": "cancel_order",
  "order_number": "<order_number>",
  "reason": "<reason or default>"
}}  

⚠️ Rules for tool usage:
- `action` must always be `"cancel_order"`.  
- `order_number` must match exactly from SQL query results.  
- `reason` defaults to `"Customer cancelled the order"` if not provided.  
- Never fabricate or guess `order_number`.  

Inside the tool:  
1. Update **Orders** → set `status = "CANCELLED"`.  
2. Insert into **OrderAudit** (old → new status).  
3. Restore stock in **Inventory** and log into **InventoryAudit**.  
4. Send cancellation confirmation email to `customer_email`.  
5. Calculate refund = `ordered_quantity × price`.  

✅ Example Successful Output:  
{{ "output": "✅ Your order (ID: ORD-1234ABCD) has been cancelled successfully. A refund of $199.99 will be processed within 5 working days. 💳" }}  

❌ Example Failure Outputs:  
- Already cancelled:  
  {{ "output": "⚠️ Order ORD-1234ABCD is already cancelled." }}  
- Delivered/Shipped:  
  {{ "output": "⚠️ Order ORD-1234ABCD cannot be cancelled because it has already been shipped/delivered." }}  
- Invalid ID:  
  {{ "output": "❌ Invalid order ID. Please check and try again." }}  
- Unexpected error:  
  {{ "output": "❌ Unable to process the cancellation at this time. Please try again later." }}  

---

### 4. Error Handling
- Always handle gracefully.  
- If tool returns empty or error → return a polite JSON message.  
- Never expose SQL or raw tool JSON directly.  

---

### 5. Conversation Rules
- Always validate `order_number` first before cancellation.  
- Never cancel without explicit **yes**.  
- Always produce a JSON with `"output"` key.  
- Be polite, professional, and clear.  

---

### 6. Example User Queries
- "Cancel my order ORD-5001"  
- "I want to cancel order ORD-7777"  
- "Can you check order number ORD-1234?"  
- "Yes, cancel it"  
- "No, keep it active"  

---

### 7. Final Answer Rules
- Always return valid JSON with only one key `"output"`.  
- Never return raw SQL, Python, or tool call JSON.  
- Always interpret results into polite, human-readable messages.  
"""


    prompt = ChatPromptTemplate.from_messages([
        ("system", instructions),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}")
    ])

    # Create agent
    agent = create_tool_calling_agent(llm=llm, tools=all_tools, prompt=prompt)

    agent_executor = AgentExecutor(
        agent=agent,
        tools=all_tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=12,
        return_intermediate_steps=False,
    )

    agent_with_memory = RunnableWithMessageHistory(
        runnable=agent_executor,
        get_session_history=get_by_session_id,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    print("Combined Order Cancellation Agent created successfully!")
    return agent_with_memory


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def handle_order_cancellation(session_id: str, user_input: str):
    """
    Handle order check and cancellation request.
    """

    print(f"\nOrder Cancellation Agent Processing: '{user_input}'")
    print("=" * 60)

    try:
        agent = create_order_cancellation_agent()

        result = await agent.ainvoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}}
        )

        print("ORDER CANCELLATION AGENT RESULT", result)

        if isinstance(result, dict):
            output_raw = result.get("output") or result.get("text") or str(result)
        else:
            output_raw = str(result)

        output_raw = literal_eval(output_raw.strip())
        print(f"Agent output: {output_raw}")

        if not output_raw:
            return {
                "output": "Please check the query or try again.",
                "success": False,
                "session_id": session_id
            }
        else:
            return {
                "output": output_raw["output"],
                "success": True,
                "session_id": session_id
            }

    except Exception as e:
        print(f"Exception in handle_order_cancellation: {str(e)}")
        return {
            "output": f"Error in Order Cancellation Agent: {str(e)}",
            "success": False,
            "session_id": session_id
        }
