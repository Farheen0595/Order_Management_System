# order_placement_agent.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

# LangChain SQL Toolkit imports
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit

from app.agents.memory import get_by_session_id
from app.config.settings import settings

# Import your existing custom tools
from app.tools.order_tools import (
    CreateOrderTool,
    OrderAuditTool,
    InventoryUpdateTool,
    SendConfirmationEmailTool
)


def create_order_placement_agent():
    """
    Order Placement Agent with LangChain SQL Toolkit + Your Custom Tools
    
    This agent can:
    1. Check products using SQL Toolkit (sql_db_query, sql_db_schema, etc.)
    2. Place orders using your custom tools in sequence
    """
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model=settings.DEFAULT_MODEL,
        api_key=settings.GEMINI_API_KEY,
        max_tokens=2000,
        temperature=0  # Deterministic for order processing
    )
    
    # Setup SQL Database connection using your settings
    database_url = f"mysql+pymysql://{settings.DB_USERNAME}:{settings.DB_PASSWORD}@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}"
    
    print(f" Attempting database connection...")
    print(f"URL: mysql+pymysql://{settings.DB_USERNAME}:***@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}")
    
    try:
        db = SQLDatabase.from_uri(database_url)
        # Test the connection
        tables = db.get_usable_table_names()
        print(f"Database connection established")
        print(f"Available tables: {tables}")
    except Exception as e:
        print(f" Database connection failed: {e}")
        print(f" Check your database settings in app/config/settings.py")
        db = None
    
    # Create LangChain SQL Toolkit
    if db:
        sql_toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        sql_tools = sql_toolkit.get_tools()
        print(f"SQL Toolkit created with {len(sql_tools)} tools:")
        for tool in sql_tools:
            print(f"   - {tool.name}: {tool.description}")
    else:
        sql_tools = []
        print("No SQL tools available due to database connection issue")
    
    # Your custom order workflow tools
    custom_tools = [
        CreateOrderTool(),         # Create order in orders table
        OrderAuditTool(),          # Log order audit
        InventoryUpdateTool(),     # Update inventory and log audit  
        SendConfirmationEmailTool() # Send confirmation email
    ]
    
    print(f"Custom tools loaded: {[tool.name for tool in custom_tools]}")
    
    # Combine all tools
    all_tools = sql_tools + custom_tools
    print(f"🔧 Total tools available: {len(all_tools)}")
    
    # Detailed system instructions
    instructions = """
You are an Order Placement Agent with access to SQL database tools and custom order workflow tools.

**YOUR CAPABILITIES:**

**SQL Database Tools (LangChain SQL Toolkit):**
- sql_db_query: Execute SQL queries to check products, inventory, get product details
- sql_db_schema: Get database table structure information  
- sql_db_list_tables: List all available database tables

**Custom Order Workflow Tools:**
- create_order: Create new order record in orders table
  Parameters: product_id (int), quantity (int), status (str), remarks (str, optional)
- order_audit: Log order audit trail with status changes  
  Parameters: order_id (int), prev_status (str), new_status (str), remarks (str, optional)
- update_inventory: Update inventory quantities and log inventory audit
  Parameters: product_id (int), changeType (str), quantityChanged (int), remarks (str, optional)
- send_email: Send order confirmation email to customer
  Parameters: to (str), subject (str), body (str)

**DATABASE SCHEMA:**
- **Inventory Table**: product_id, product_name, brand, category, quantity_available, price, currency, status
- **orders Table**: order_id, product_id, quantity, status, remarks, order_date  
- **order_audit Table**: audit_id, order_id, previousStatus, newStatus, timestamp, remarks
- **inventory_audit Table**: audit_id, product_id, quantity_available, changeType, quantityChanged, timestamp, remarks

**HANDLING DIFFERENT QUERY TYPES:**

**1. Product Information Queries:**
Examples: "Does iPhone exist?", "Show Apple products", "What's the price of Samsung TV?"
- Use sql_db_query to search Inventory table
- Format results in user-friendly way
- Show: product name, brand, availability, price

**2. Order Placement Queries:**  
Examples: "Order 2 iPhones for john@email.com", "I want to buy Samsung TV"
- **Step 1**: Use sql_db_query to check product exists and has sufficient stock
- **Step 2**: MANDATORY - Follow ALL 4 steps in exact sequence (DO NOT STOP after step 2):
  1. create_order(product_id, quantity, status='pending', remarks)
  2. order_audit(order_id, prev_status='none', new_status='pending', remarks)  
  3. update_inventory(product_id, changeType='REMOVE', quantityChanged, remarks)
  4. send_email(to=customer_email, subject='Order Confirmation', body=details)

**CRITICAL: You MUST complete ALL 4 custom tools for every order. Do not stop after create_order!**

**ORDER COMPLETION REQUIREMENTS:**
For EVERY order placement request, you MUST execute ALL 5 steps:
1. sql_db_query (check product and stock)
2. create_order (create order record) 
3. order_audit (log audit trail)
4. update_inventory (deduct stock)
5. send_email (send confirmation)

**DO NOT consider the order complete until ALL 5 steps are finished!**
Even if create_order succeeds, you must continue with steps 3, 4, and 5.
Each step depends on the previous step's output.

**STEP CHAINING:**
- Use order_id from create_order result in order_audit
- Use same product_id in update_inventory as create_order  
- Include order details from all steps in email body

**IF ANY STEP FAILS:**
- Explain which step failed and why
- Do not continue to next steps if previous step failed
- Provide clear error message to user

**order_audit tool:**
- order_id: integer (from create_order result)
- prev_status: string (use "none" for new orders) 
- new_status: string (use "pending" for new orders)
- remarks: string (optional, default: "Order placed")

**update_inventory tool:**
- product_id: integer (same as create_order product_id)
- changeType: string (use "REMOVE" for order deductions)  
- quantityChanged: integer (same as order quantity)
- remarks: string (optional, describe the deduction)

**send_email tool:**
- to: string (customer email address)
- subject: string (order confirmation subject)
- body: string (detailed order information)

**DATA TYPE VALIDATION:**
- All IDs must be integers, not strings
- Quantities must be positive integers
- Status values must be exact strings ("pending", "none", "REMOVE")
- Email addresses must be valid string format

**EXAMPLE SUCCESSFUL ORDER FLOW:**
User: "Order 2 iPhones for john@email.com"

1. sql_db_query("SELECT product_id, product_name, quantity_available, price FROM Inventory WHERE product_name LIKE '%iPhone%' AND status='active' LIMIT 1")
   → Result: product_id=1, product_name='iPhone 14', quantity_available=10, price=999.99

2. Check: quantity_available (10) >= requested (2) 

3. create_order(product_id=1, quantity=2, status="pending", remarks="Customer order via agent")
   → Result: order_id=12345

4. order_audit(order_id=12345, prev_status="none", new_status="pending", remarks="Order created successfully")

5. update_inventory(product_id=1, changeType="REMOVE", quantityChanged=2, remarks="Order 12345 inventory deduction")

6. send_email(to="john@email.com", subject="Order Confirmation #12345", body="Your order for 2 iPhone 14 has been placed successfully. Total: $1999.98")

7. Provide confirmation: "Order placed successfully! Order ID: 12345, Total: $1999.98"

**EXAMPLE SQL QUERIES FOR PRODUCT SEARCH:**

**Brand-based search:**
- "Does Samsung TV exist?" → `SELECT * FROM Inventory WHERE brand LIKE '%Samsung%' AND product_name LIKE '%TV%' AND status='active'`
- "Show Apple products" → `SELECT * FROM Inventory WHERE brand LIKE '%Apple%' AND status='active'`

**Product name search:**  
- "Find LED TV" → `SELECT * FROM Inventory WHERE product_name LIKE '%LED%' AND product_name LIKE '%TV%' AND status='active'`

**Combined search (recommended):**
- "Samsung Smart TV" → `SELECT * FROM Inventory WHERE (brand LIKE '%Samsung%' AND product_name LIKE '%TV%') OR (product_name LIKE '%Samsung%' AND product_name LIKE '%TV%') AND status='active'`

Always use LIKE '%term%' for flexible matching since users may not know exact product names.

**ERROR HANDLING:**
- If product not found → "Product not found in inventory"
- If insufficient stock → "Insufficient stock. Available: X, Requested: Y"  
- If any tool fails → Explain the specific issue and stop the workflow
- Always be helpful and provide clear status updates

**RESPONSE FORMAT:**
- Use emojis for better readability
- Provide clear, actionable information
- For product queries: Show formatted product details
- For orders: Show step-by-step progress and final confirmation
"""
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", instructions),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}")
    ])
    
    # Create the agent
    agent = create_tool_calling_agent(llm=llm, tools=all_tools, prompt=prompt)
    
    # Create agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=all_tools,
        verbose=True,  # Set to True for debugging
        handle_parsing_errors=True,
        max_iterations=12,  # SQL query + 4 custom tools + reasoning steps
        return_intermediate_steps=True
    )
    
    # Add conversation memory
    agent_with_memory = RunnableWithMessageHistory(
        runnable=agent_executor,
        get_session_history=get_by_session_id,
        input_messages_key="input",
        history_messages_key="chat_history",
    )
    
    print("Order Placement Agent created successfully!")
    return agent_with_memory


# Main handler function
async def handle_order_placement(session_id: str, user_input: str):
    """
    Handle order placement queries using SQL Toolkit + Custom Tools
    
    Args:
        session_id: Unique session identifier
        user_input: User's query (product question or order request)
        
    Returns:
        Dictionary with output, success status, and metadata
    """
    
    print(f"\n Order Placement Agent Processing: '{user_input}'")
    print("=" * 60)
    
    try:
        # Create the agent
        agent = create_order_placement_agent()
        
        # Process the request
        result = await agent.ainvoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}}
        )
        
        # Extract results
        output = result.get("output", "No output received")
        intermediate_steps = result.get("intermediate_steps", [])
        
        print(f" Processing completed successfully!")
        print(f" Final output: {output}")
        
        if intermediate_steps:
            print(f" Tools used: {len(intermediate_steps)} steps")
            for i, (action, observation) in enumerate(intermediate_steps, 1):
                print(f"   {i}. {action.tool}: {action.tool_input}")
        
        return {
            "output": output,
            "success": True,
            "agent_type": "order_placement_sql_toolkit_custom_tools",
            "tools_used": len(intermediate_steps),
            "session_id": session_id
        }
        
    except Exception as e:
        error_msg = f" Error in Order Placement Agent: {str(e)}"
        print(error_msg)
        
        return {
            "output": error_msg,
            "success": False,
            "agent_type": "order_placement_sql_toolkit_custom_tools",
            "error": str(e),
            "session_id": session_id
        }

