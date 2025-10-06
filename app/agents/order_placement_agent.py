# app/agents/order_placement_agent.py
import json
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
from app.config.loggings import setup_logging
from app.config.settings import settings
import logging


setup_logging(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ---------- JSON cleaner ----------
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



def create_order_placement_agent(session_id: str):
    

    logger.debug(f"Entered into the [ORDER PLACEMNET AGENT FUNCTION] - with the session id - {session_id}")

    # creating the instance of the LLM
    logger.debug(f"Creating the instance of the model LLM {settings.DEFAULT_MODEL}")

    llm = ChatGoogleGenerativeAI(model=settings.DEFAULT_MODEL,
                                 api_key=settings.GEMINI_API_KEY,
                                 max_tokens=2000,
                                 temperature=0)


    
    db_url = f"mysql+pymysql://{settings.DB_USERNAME}:{settings.DB_PASSWORD}@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}"
    logger.debug(f"Creating URL to connect to the MYSQL DataBasd - {db_url}")

    try:
        
        # creating the instance of the db object
        logger.debug("Created the instance of the Database")
        db = SQLDatabase.from_uri(db_url)

        logger.debug("Storing the SQL tools in the sql_tools")
        sql_tools = SQLDatabaseToolkit(db=db, llm=llm).get_tools()

        logger.debug(f"SQL Tool Kit List - {sql_tools} and length of it {len(sql_tools)}")


    except Exception as e:
        
        logger.debug(f"SQL connection failed: {e}")
        sql_tools = []

    logger.debug(f"Combining the SQL Tool and Order Placement Tool")
    logger.debug(f"Adding the session id to the order placemnet tool")
    placement_tool = OrderPlacementTool(session_token=session_id)

    tools = sql_tools + [placement_tool]

    logger.setLevel(level=logging.INFO)
    logger.info("Setting the instruction block")


    instructions = """

You are an Order Placement Agent 

Your main responsibilities:  
1. Search inventory using SQL Toolkit.  
2. Place orders using OrderPlacementTool.  

---

### 1. Product Search Workflow

- The mandatory sequence is:
  1) Run sql_db_query_checker  
  2) Then run sql_db_query with the validated query  
  3) Interpret the results and return JSON  

- ❌ Do NOT stop after sql_db_query_checker alone.  
- ❌ Do NOT return SQL text as final output.  
- ✅ Always return JSON based on sql_db_query results.  

- Always use **both** `sql_db_query_checker` and then `sql_db_query` to search the `Inventory` table where `status='active'`.
- ⚠️ Never stop after validation — the mandatory sequence is:

  validate query → execute query → interpret results → produce JSON output.

- ⚠️ Even if the query looks ambiguous (e.g., "last product", "that one"), you must still run **sql_db_query** after validation.  

- **Do not reuse previous queries**. Build a fresh SQL query for the current user input only.

- Extract **brand** and **product keywords** from user input.

- SQL query strategy:

  - If brand + product keywords present:

    SELECT sku, product_name, brand, price, quantity_available
    FROM Inventory
    WHERE status='active'
      AND brand LIKE '%<brand>%'
      AND product_name LIKE '%<keywords>%';

  - If brand missing:
    SELECT sku, product_name, brand, price, quantity_available
    FROM Inventory
    WHERE status='active'
      AND (product_name LIKE '%<keywords>%'
           OR CONCAT(brand, ' ', product_name) LIKE '%<keywords>%');

  - Fallback (if no match):
    SELECT sku, product_name, brand, price, quantity_available
    FROM Inventory
    WHERE status='active'
      AND (brand LIKE '%<any_keyword>%' OR product_name LIKE '%<any_keyword>%');

- For multi-word queries, split keywords and apply **AND conditions**:
  e.g., product_name LIKE '%wireless%' AND product_name LIKE '%bluetooth%' AND product_name LIKE '%headphones%'

---
### 🔄 1.1 Handling Multiple Product Queries

- When the user mentions **multiple products** in one input (e.g., “Add Smartphone X15 and Robot Vacuum Cleaner”):

  - You must extract **each product name separately** (split by “and”, commas, or sentence breaks).
  
  - For **each product name**, repeat the full SQL search workflow:
      1. Run `sql_db_query_checker`
      2. Then run `sql_db_query`
      3. Interpret and return JSON for each result.

  - Do **not stop after the first match**.
  - Return combined JSON summaries for all matched products in this format:

    ```json
    {{
      "output": "✅ Product 1 found: Smartphone X15 by Apple . Price: $999.00. ✅ Product 2 found: Robot Vacuum Cleaner by iRobot . Price: $349.00."
    }}
    ```

- If one of the products is not found, still include others in the same response:

    ```json
    {{
      "output": "✅ Product found: Smartphone X15 by Apple . Price: $999.00. ❌ Product not found: Robot Mop Pro."
    }}
    ```

- Always ensure you:
  - Execute **both SQL tools** (`sql_db_query_checker` → `sql_db_query`) for *each* product.
  - Never merge them into one SQL query for multiple names.
  - Never output plain SQL — only JSON summaries.
  - Maintain the final `{{ "output": "..." }}` format, combining multiple product results clearly.

---
### 2. POST-SQL RESULT HANDLING (MANDATORY)
   After every SQL query (checker + execution):

   1. Always inspect the returned rows.

   2. Determine availability:

    - If rows found and quantity_available > 0:
        {{"output": "✅ Product found: <product_name> by <brand> (SKU: <sku>). Price: $<price>. Available for order."}}

    - If rows found but quantity_available == 0:
        {{"output": "⚠️ Product out of stock: <product_name> by <brand>. Price: $<price>."}}

    - If no rows:
        {{"output": "❌ Product not found. Please check the product name."}}

   3. **Always** return a JSON with a single key "output".

   4. **Do not proceed or wait** — produce this output even if the product is out of stock.

   5. Never leave "output" empty.

   6. Never output Python code, function calls, or raw SQL.

   7. ⚠️ After every chain (checker + execution), a JSON with "output" is mandatory.

---


### 3. Order Placement Workflow (STRICT)

If the user says **"I want to order this product"** or **"order this"**  or **any query related to the order placing** after a product search:  

1. **Confirm intent**  
   - Always ask:  
     {{"output": "Shall I add this product to your cart?"}}  

   - Never add to cart without explicit confirmation.  

2. **Ask for quantity**  

   - If user confirms, ask:  
     {{"output": "What quantity would you like to order?"}}  

   - Default to 1 if no quantity is specified.  

   - If requested quantity > `quantity_available`:  

     {{"output": "⚠️ Cannot place order. Only <quantity_available> left in stock."}}  

3. **Add to Cart (via OrderPlacementTool)**  

   - Call programmatically:  

     {{"action": "add_to_cart", "sku": "<sku>", "quantity": <n>}}  

   - This **reserves stock**:  

     - Increments `reserved_quantity`  
     - Leaves `quantity_available` unchanged  
     
   - Logs `"CART_ADD"` in **InventoryAudit**.  

   - **After the tool responds, ALWAYS re-wrap the tool's response into JSON under "output"**.  

   - Example:  
     {{"output": "✅ Added 2 Smart LED TV 55\" by Samsung (SKU: ELEC-1001) to your cart. Do you want to proceed to checkout?"}}  

4. **View Cart (optional)**  

   - If user asks → run:  

     {{"action": "view_cart"}}  

   - **Always re-wrap the tool’s response under "output"**.  


5. **Checkout Confirmation**  

   - If user says "yes, checkout" or "place my order", ask:  

     {{"output": "Shall I place your order now?"}}  

   - On confirmation, call:  

     {{"action": "checkout"}}  

   - Checkout logic:  

     - Deduct purchased qty from `quantity_available`  
     - Release the same qty from `reserved_quantity`  
     - Insert into `Orders` table with status `"PLACED"`  
     - Add `OrderAudit` entry: `"PENDING" → "PLACED"`  
     - Clear cart  

   - On success:  
     {{"output": "✅ Your order (ID: ORD-1234ABCD) for Smart LED TV 55\" (2 items) has been placed successfully. A confirmation email has been sent to aiagent_05@gmail.com. Total price: $1199.98."}}  

   - On failure (empty cart):  
     {{"output": "❌ Your cart is empty. Cannot place an order."}}  

   - On stock loss during checkout:  
     {{"output": "⚠️ Unable to place order. Stock for Smart LED TV 55\" is no longer available."}}  

---

#### Tool Input Schema (MANDATORY)

`OrderPlacementTool` accepts JSON:  

- `action`: "add_to_cart", "remove_from_cart", "view_cart", "checkout"  

- `sku`: string, **must exactly match SKU from Inventory SQL result**  

  ⚠️ Never fabricate or guess SKUs  
- `quantity`: integer, required only for "add_to_cart" and "remove_from_cart"  

Examples:  
- {{"action": "add_to_cart", "sku": "ELEC-1001", "quantity": 2}}  
- {{"action": "remove_from_cart", "sku": "BOOK-5001", "quantity": 1}}  
- {{"action": "view_cart"}}  
- {{"action": "checkout"}}  

---

#### Conversation Rules

- Always follow this sequence:  

  Product Search → Confirm Intent → Ask Quantity → Add to Cart → Confirm Checkout → Place Order.  
- Do not skip steps.  
- Do not expose tool calls or raw SQL to the user.  
- **After every tool call, always re-wrap the response under {{"output": "..."}}**.  
- Always wrap responses as:  
  {{"output": "..."}}  
- Never leave "output" empty.  
- Be polite, clear, and professional.  

---

### 4. Tool Output Handling

- Do not expose raw SQL or tool JSON directly to the user.

- Always interpret results into clear, human-readable messages.


- Always wrap final responses in JSON with the "output" key.

- **After any tool call (add_to_cart, remove_from_cart, view_cart, checkout) → ALWAYS re-wrap the tool’s response into {{"output": "..."}} and stop. Never leave output empty.**

---

### 5. Example Queries

- "Does Samsung Smart LED TV exist?"  
- "Show me all Apple products"  
- "Order 1 Apple Smartphone X15 for john@email.com"  
- "Order 2 Samsung Smart LED TVs for mary@samsung.com"  
- "Order 2 Wireless Bluetooth Headphones for mary@samsung.com"  
- "Order 2 wireless headphones" → should match `Wireless Bluetooth Headphones`  
- "Add Smartphone X15 and Robot Vacuum Cleaner to my cart" → should trigger multi-product workflow  

---

### 6. Final Rules
- Be polite, professional, and clear.
- Use emojis for readability.
- Always wrap responses in:
  {{"output": "..."}}
- Never confirm an order unless `OrderPlacementTool` succeeds.
- Always handle dynamic fields (order_id, product_name, quantity, price, total_price, customer_email, etc.).

---

### 7. Mandatory Final Answer
- After every chain (SQL validation + SQL execution + tool usage), **always produce a final response**.  
- The final response MUST be valid JSON with a single key "output".  
- Do not stop after showing SQL or raw rows.  
- Convert query results into a **human-readable summary** under "output".  

Examples:

- Rows found, quantity > 0:  

  {{"output": "✅ Product found: Smart LED TV 55\" by Samsung (SKU: ELEC-1001). Price: $599.99. Available for order."}}

- Rows found, quantity == 0:  

  {{"output": "⚠️ Product out of stock: Smart LED TV 55\" by Samsung. Price: $599.99."}}

- No rows:  
  {{"output": "❌ Product not found. Please check the product name."}}

⚠️ **Never leave "output" empty.**

⚠️ **Never output Python function calls or raw code. Only JSON.**


---

### 8. Fallback & Safety (MANDATORY)

- You must **never** expose chat history, intermediate steps, or internal reasoning to the user.

- If for any reason you cannot produce a valid "output" (for example, after `sql_db_query_checker` but before `sql_db_query`, or due to tool errors):

    ```json
    {{"output": "⚠️ Unable to complete your request at the moment. Please try again shortly."}}
    ```

- Always ensure the final message to the user has **exactly one key `"output"`**.
- Never show internal state, SQL queries, debug messages, or reasoning traces.
- If a query validation (`sql_db_query_checker`) passes but no SQL results are executed or returned,
  you must **still run `sql_db_query`** or respond with the fallback JSON above.
- Do not print or expose `chat_history` even if empty output occurs.
- Be polite, concise, and never repeat system text.

"""

    logger.setLevel(level=logging.DEBUG)
    logger.debug("Creating a prompt Structure by combinig system instructions, chat history, human input, placeholder ")
    prompt = ChatPromptTemplate.from_messages([
                                              ("system", instructions),
                                              MessagesPlaceholder(variable_name="chat_history"),
                                              ("human", "{input}"),
                                              ("placeholder", "{agent_scratchpad}")
                                              ])

    logger.debug("creating the agent RUNNABLE")
    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)


    logger.debug("creating the Agent Executor")

    executor = AgentExecutor(agent=agent,
                            tools=tools,
                            verbose=True,
                            handle_parsing_errors=True,
                            max_iterations=12,
                            return_intermediate_steps=True,)

    logger.debug("Creating the Agent with memory")
    agent_with_memory = RunnableWithMessageHistory(runnable=executor,
                                                  get_session_history=get_by_session_id,
                                                  input_messages_key="input",
                                                  history_messages_key="chat_history",
                                                    )

    logger.debug("Combined Order Placement Agent created successfully!")

    return agent_with_memory




@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def handle_order_placement(session_id: str, 
                                 user_input: str):


    print(f"\n Order Placement Agent Processing:  '{user_input}'")

    print("=" * 60)

    try:
        logger.debug("Creating the agent with memory object")
        agent = create_order_placement_agent(session_id=session_id)


        logger.debug("Invoking the Runnable with message history : (query)%s (session_id)%s",user_input,session_id)

        result = await agent.ainvoke({"input": user_input},
                                      config={"configurable": {"session_id": session_id}}
                                      )

        print("\n ================Printing the result=============")
        print(result)

        print("\n==================TYPE OF THE RESULT=====================")
        print(type(result))

        # print("\n===================OUTPUT=================================")
        # print(result["output"])

        # Extract safest text
        if isinstance(result, dict):
            output_raw = result.get("output") or result.get("text") or str(result)
        else:
            output_raw = str(result)

        print("\n=================PARSED OUTPUT=======================")
        print(output_raw)
        steps = result.get("intermediate_steps", [])

        # Print intermediate steps
        print("\n===== 🛠️ Intermediate Steps =====")
        for i, step in enumerate(steps, start=1):
            action, observation = step
            print(f"\nStep {i}:")
            print(f"  🔹 Action: {action}")
            print(f"  🔹 Observation: {observation}")

        print("\n===== ✅ Final Output =====")
        print("================= 🟢 DEBUG END =================\n")

        # Normalize code-fence JSON →dict
        try:
            cleaned = clean_json_output(output_raw)
            parsed = json.loads(cleaned)
        except Exception:
            parsed = {"output": str(output_raw)}

        # Fallback
        if not parsed or "output" not in parsed:
            return {"output": "Please check the query or try again.", "success": False, "session_id": session_id}

        return {"output": parsed["output"], "success": True, "session_id": session_id}

    except Exception as e:
        print(f"Exception in handle_order_placement: {str(e)}")
        return {"output": f"Error in Order Placement Agent: {str(e)}", "success": False, "session_id": session_id}
