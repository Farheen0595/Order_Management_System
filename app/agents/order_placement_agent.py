# order_placement_agent.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit

from app.agents.memory import get_by_session_id
from app.config.settings import settings
from app.tools.order_placement_tools import OrderPlacementTool
from tenacity import retry, stop_after_attempt, wait_fixed
import json
from ast import literal_eval


def create_order_placement_agent():

    """
    Combined Order Placement Agent:
    - SQL Toolkit for inventory/product queries
    - OrderPlacementTool for creating orders
    """

    #  LLM
    llm = ChatGoogleGenerativeAI(
        model=settings.DEFAULT_MODEL,
        api_key=settings.GEMINI_API_KEY,
        max_tokens=2000,
        temperature=0  )


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


    custom_tools = [OrderPlacementTool()]


  
    all_tools = sql_tools + custom_tools

    instructions = """
You are an Order Placement Agent.  
Your main responsibilities:  
1. Search inventory using SQL Toolkit.  
2. Place orders using OrderPlacementTool.  

---

### 1. Product Search Workflow
- Always use **both** `sql_db_query_checker` and then `sql_db_query` to search the `Inventory` table where `status='active'`.
- Never stop after validation. The mandatory sequence is:
  validate query → execute query → interpret results → produce JSON output.
- **Do not reuse previous queries**. Build a fresh SQL query for the current user input only.
- Extract **brand** and **product keywords** from user input.
- SQL query strategy:
  - If brand + product keywords present:
    SELECT product_id, product_name, brand, price, quantity_available
    FROM Inventory
    WHERE status='active'
      AND brand LIKE '%<brand>%'
      AND product_name LIKE '%<keywords>%';
  - If brand missing:
    SELECT product_id, product_name, brand, price, quantity_available
    FROM Inventory
    WHERE status='active'
      AND (product_name LIKE '%<keywords>%'
           OR CONCAT(brand, ' ', product_name) LIKE '%<keywords>%');
  - Fallback (if no match):
    SELECT product_id, product_name, brand, price, quantity_available
    FROM Inventory
    WHERE status='active'
      AND (brand LIKE '%<any_keyword>%' OR product_name LIKE '%<any_keyword>%');

- For multi-word queries, split keywords and apply **AND conditions**:
  e.g., product_name LIKE '%wireless%' AND product_name LIKE '%bluetooth%' AND product_name LIKE '%headphones%'

---
### POST-SQL RESULT HANDLING (MANDATORY)
   After every SQL query (checker + execution):
   1. Always inspect the returned rows.
   2. Determine availability:
    - If rows found and quantity_available > 0:
        {{"output": "✅ Product found: <product_name> by <brand>. Price: $<price>. Available for order."}}
    - If rows found but quantity_available == 0:
        {{"output": "⚠️ Product out of stock: <product_name> by <brand>. Price: $<price>."}}
    - If no rows:
        {{"output": "❌ Product not found. Please check the product name."}}
   3. **Always** return a JSON with a single key "output".
   4. **Do not proceed or wait** — produce this output even if the product is out of stock.
   5. Never leave "output" empty.
   6. Never output Python code, function calls, or raw SQL.

---

### 3. Order Placement Workflow
- Only trigger if product exists AND `quantity_available > 0`.
- Reuse retrieved `product_id`, `product_name`, and `brand`.
- Collect missing details:
  - Quantity (must be >0 and ≤ `quantity_available`)  
  - Customer email (default: `aiagent_05@gmail.com` if missing)
- Validate inputs and reject invalid quantities.
- If requested quantity > `quantity_available`:
  {{ "output": "⚠️ Cannot place order. Product out of stock: <product_name> by <brand>. Price: $<price>." }}
- **Never output Python code, function calls, or raw tool calls.**
- Always call `OrderPlacementTool` programmatically and convert output into **polite JSON** under `"output"` key.

✅ Example (success):
{{ "output": "✅ Your order (ID: 12345) for Wireless Bluetooth Headphones (2 items) has been placed successfully. A confirmation email has been sent to mary@samsung.com. Total price: $399.98." }}

❌ Example (failure / insufficient stock):
{{ "output": "❌ Unable to place order due to insufficient stock. Please try a smaller quantity." }}

---

### 4. Tool Output Handling
- Do not expose raw SQL or tool JSON directly to the user.
- Always interpret results into clear, human-readable messages.
- Always wrap final responses in JSON with the `"output"` key.

---

### 5. Conversation Rules
- Detect user intent:
  - Product check → return inventory info
  - Order request → validate & place order
- If user says "no" → reply:
  {{ "output": "🙏 Thank you! Let me know if you need anything else." }}
- Stop once valid data is retrieved. Avoid unnecessary loops.
- Always return **an output**, even if product is out-of-stock or quantity is zero.

---

### 6. Example Queries
- "Does Samsung Smart LED TV exist?"  
- "Show me all Apple products"  
- "Order 1 Apple Smartphone X15 for john@email.com"  
- "Order 2 Samsung Smart LED TVs for mary@samsung.com"  
- "Order 2 Wireless Bluetooth Headphones for mary@samsung.com"  
- "Order 2 wireless headphones" → should match `Wireless Bluetooth Headphones`  

---

### 7. Final Rules
- Be polite, professional, and clear.
- Use emojis for readability.
- Always wrap responses in:
  {{ "output": "..." }}
- Never confirm an order unless `OrderPlacementTool` succeeds.
- Always handle dynamic fields (order_id, product_name, quantity, price, total_price, customer_email, etc.).

---

### 8. Mandatory Final Answer
- After every chain (SQL validation + SQL execution + tool usage), **always produce a final response**.  
- The final response MUST be valid JSON with a single key `"output"`.  
- Do not stop after showing SQL or raw rows.  
- Convert query results into a **human-readable summary** under `"output"`.  

Examples:
- Rows found, quantity > 0:  
  {{ "output": "✅ Product found: Smart LED TV 55\" by Samsung. Price: $599.99. Available for order." }}
- Rows found, quantity == 0:  
  {{ "output": "⚠️ Product out of stock: Smart LED TV 55\" by Samsung. Price: $599.99." }}
- No rows:  
  {{ "output": "❌ Product not found. Please check the product name." }}

⚠️ **Never leave `"output"` empty.**
⚠️ **Never output Python function calls or raw code. Only JSON.**
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

    print(" Combined Order Placement Agent created successfully!")
    return agent_with_memory



@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def handle_order_placement(session_id: str, user_input: str):
    """
    Handle product queries and order placement requests.
    The LLM agent is responsible for converting tool outputs (JSON)
    into human-readable responses.
    """
    print(f"\nOrder Placement Agent Processing: '{user_input}'")
    print("=" * 60)

    try:
        print(f"user query : {user_input}")
        print(f"session id: {session_id}")

        # Create the combined agent (SQL + OrderPlacementTool)
        agent = create_order_placement_agent()

        # Invoke the agent with session history
        result = await agent.ainvoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}}
        )

        print("ORDER AGENT RESULT",result)
        # Safely extract output regardless of format
        if isinstance(result, dict):
            output_raw = result.get("output") or result.get("text") or str(result)
        else:
            output_raw = str(result)

        output_raw = literal_eval(output_raw.strip())
        print(f"Agent output: {output_raw}")

        # Fallback if output is empty
        if not output_raw:
            return {
                "output": "Please check the query or try again.",
                "success": False,
                "session_id": session_id
            }

        # Successful response
        return {
            "output": output_raw["output"],
            "success": True,
            "session_id": session_id
        }

    except Exception as e:
        print(f"Exception in handle_order_placement: {str(e)}")
        return {
            "output": f"Error in Order Placement Agent: {str(e)}",
            "success": False,
            "session_id": session_id
        }
