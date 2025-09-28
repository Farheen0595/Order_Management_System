# order_placement_agent.py
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
    - SQL Toolkit for order id check queries
    - OrderCancellationTool for updating orders and inventory
    """

    #  LLM
    llm = ChatGoogleGenerativeAI(
        model=settings.DEFAULT_MODEL,
        api_key=settings.GEMINI_API_KEY,
        max_tokens=2000,
        temperature=0)


    # Connect to SQL Database
    database_url = f"mysql+pymysql://{settings.DB_USERNAME}:{settings.DB_PASSWORD}@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}"

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

YYou are an Order Cancellation Agent.  
You have two main capabilities:  
1. Check order existence using SQL Toolkit.  
2. Cancel orders using OrderCancellationTool.  

---

### 1. Order Validation Workflow
- Always use the tools `sql_db_query_checker` and `sql_db_query`.  
- Query the `Orders` table to check if the order_id exists and is active.  

SQL query example:  
SELECT order_id, product_id, quantity, status, remarks  
FROM Orders  
WHERE order_id = <order_id>;  

- If no result found:  
  {{ "output": "❌ Invalid order ID. Please provide a valid order ID." }}  

- If order exists, return to user in this **polite, human-readable format**:  
  {{ "output": "📦 Order found! Order ID: <order_id>, Status: <status>, Quantity: <quantity>. Do you want to cancel this order?" }} 

- Always include emojis for readability.

---

### 2. User Confirmation Workflow
- If user responds **yes** → proceed to cancellation workflow.  
- If user responds **no** → respond politely:  
  {{ "output": "🙏 Okay, no cancellation made. Do you need any other assistance?" }}  
- Do not proceed with cancellation without explicit **yes** from the user.

---

### 3. Order Cancellation Workflow
- Trigger `OrderCancellationTool` with the following inputs:
  - `order_id` (from user input)  
  - `reason` (use default "Customer Cancelled the Order" if user does not provide)  
  - `email_address` (use default "aiagent_05@gmail.com" if missing)  

Inside the cancellation tool, perform:
1. Update **Order Table** → set `status = "Cancelled"`, `quantity = 0`.  
2. Insert record into **Order Audit** (track previous status → Cancelled).  
3. Restore stock in **Inventory** and log in **Inventory Audit**.  
4. Send cancellation confirmation email to customer.  
5. Calculate `total_refund` = `ordered_quantity × price`.  

Return a **structured JSON** object from the tool:  
{{
  "order": {{
    "order_id": <order_id>,
    "status": "Cancelled"
  }},
  "product_name": "<product_name>",
  "email": {{ "to": "<customer_email>" }},
  "total_refund": <refund_amount>
}}

- Convert the tool output into a **human-readable, polite message**:  
{{ "output": "✅ Your order no #<order_id> has been cancelled successfully. A refund of <refund_amount> will be credited within 5 working days. 💳" }}  

- Always handle unknown fields dynamically (e.g., order_id, product_name, customer_email, total_refund).

---

### 4. Error Handling
- If the order is already cancelled or cannot be cancelled:  
  {{ "output": "⚠️ This order has already been cancelled or cannot be cancelled." }}  
- Any unexpected errors → respond politely:  
  {{ "output": "❌ Unable to process the cancellation at this time. Please try again later." }}

---

### 5. Conversation Rules
- Always validate order_id first.  
- Never attempt cancellation without explicit **yes** from the user.  
- Stop immediately if order_id is invalid.  
- After successful cancellation → confirm with success message.  
- Maintain polite, professional tone with emojis for clarity.  

---

### 6. Example User Queries
- "Cancel my order #5"  
- "I want to cancel order 12 for john@example.com"  
- "Can you check order id 15?"  
- "Yes, cancel my order"  
- "No, keep my order"  

---

### 7. Final Rules
- Always wrap responses in: {{ "output": "..." }} 
- Never expose raw SQL queries or JSON to the user.  
- Always format all outputs in **clear, human-readable, polite, emoji-enhanced text**.  

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
        return_intermediate_steps=False
    )


    agent_with_memory = RunnableWithMessageHistory(
        runnable=agent_executor,
        get_session_history=get_by_session_id,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    print(" Combined Order Cancellation Agent created successfully!")
    return agent_with_memory



@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def handle_order_cancellation(session_id: str, user_input: str):

    """
    Handle order check anf cancellation request.
    The LLM agent is responsible for converting tool outputs (JSON)
    into human-readable responses.
    """

    print(f"\nOrder Cancellation Agent Processing: '{user_input}'")
    print("=" * 60)

    try:
        print(f"user query : {user_input}")
        print(f"session id: {session_id}")

        # Create the combined agent (SQL + OrderCancellationTool)
        agent = create_order_cancellation_agent()

        # Invoke the agent with session history
        result = await agent.ainvoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}}
        )

        print("ORDER CANCELLATION AGENT RESULT",result)

        # Safely extract output regardless of format
        if isinstance(result, dict):
            output_raw = result.get("output") or result.get("text") or str(result)
        else:
            output_raw = str(result)

        output_raw = literal_eval(output_raw.strip())
        
        print(f"Agent output: {output_raw}")

        print("type of the output war",type(output_raw))

        # Fallback if output is empty
        if not output_raw:
            return {
                "output": "Please check the query or try again.",
                "success": False,
                "session_id": session_id}
        else:
        # Successful response
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
            "session_id": session_id}
