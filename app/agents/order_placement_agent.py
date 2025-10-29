# app/agents/order_placement_agent.py

import json
import re
import logging
from tenacity import retry, stop_after_attempt, wait_fixed
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
import ast
from app.agents.memory import get_by_session_id
from app.config.settings import settings
from app.tools.order_placement_tools import OrderPlacementTool
from app.config.loggings import setup_logging
from app.config.constants import constants


setup_logging(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_order_placement_agent(session_id: str):
    """Create an order placement agent with SQL + Order tools."""

    logger.info(f"Creating order placement agent for session: {session_id}")

    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model=constants.DEFAULT_MODEL,
        api_key=settings.GEMINI_API_KEY,
        max_tokens=2000,
        temperature=0
    )

    # Initialize Database tools
    db_url = f"mysql+pymysql://{settings.DB_USERNAME}:{settings.DB_PASSWORD}@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}"
    try:
        db = SQLDatabase.from_uri(db_url)
        sql_tools = SQLDatabaseToolkit(db=db, llm=llm).get_tools()
        logger.info(f"SQL toolkit initialized with {len(sql_tools)} tools")
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}", exc_info=True)
        sql_tools = []

    # Order tool
    placement_tool = OrderPlacementTool(session_token=session_id)
    tools = sql_tools + [placement_tool]

    # ---------- Simplified Instructions ----------


    instructions ="""
You are an intelligent Order Placement Agent.

Your responsibilities:
1. Search the 'Inventory' table using SQL tools.
2. Manage shopping cart using OrderPlacementTool.
3. Place orders for users and generate order numbers.
4. Always return results as valid JSON with **one key**: "output".
5. Never return Python objects, tuples, or raw SQL.
6. Always provide **human-readable summaries**.

---

### Product Search

- SQL query format:
  SELECT sku, product_name, brand, price, quantity_available
  FROM Inventory
  WHERE status='active'
    AND (brand LIKE '%<brand>%' OR product_name LIKE '%<keywords>%');

- SQL results appear like:

  [("COMP-3002", "Mechanical Keyboard RGB", "Logitech", 129.99, 30)]
  
- Convert into human-readable JSON:

  {{
    "output": "✅ Product Found: SKU COMP-3002 , Name: Mechanical Keyboard RGB , Brand: Logitech , Price: 129.99 , Quantity Available: 30"
  }}

- If multiple products, list each separated by periods.

- If no record is found:
  {{
    "output": "❌ Product not found."
  }}

---

### Cart Management (OrderPlacementTool)

- Always take SKU and quantity from SQL result.Don't generate your OWN 

#### Add to Cart
- Use action: "add_to_cart" with `sku` and `quantity`.
- Validate SKU exists and stock is available.
- Return JSON summary:
  {{
    "output": "Added 2 Smart LED TV 55' to your cart. Cart now has: Smart LED TV 55' x 2 = $1199.98"
  }}

#### Remove from Cart
- Use action: "remove_from_cart" with `sku` and `quantity`.
- Update reserved quantity.
- Return JSON summary:
  {{
    "output": "Removed 1 Smart LED TV 55' from your cart. Cart now has: Smart LED TV 55' x 1 = $599.99"
  }}

#### View Cart
- Use action: "view_cart" to display cart contents.
- Include items, quantities, subtotal, total, and optional prompt to checkout.
- Example:
  {{
    "output": "Cart items:\n- Smart LED TV 55' x 2 = $1199.98\nTotal: $1199.98\nDo you want to checkout?"
  }}

---

### Checkout / Place Order

- Use action: "checkout".
- Validate:
  - Cart is not empty
  - All items have reserved quantities
  - Enough stock exists
- Generate unique order number: ORD-XXXXXXXX
- Deduct inventory quantities and release reserved amounts
- Save records in Orders, InventoryAudit, and OrderAudit
- Ask email of the user before placing the order don't generate random email
- Send confirmation email to the user's email ID (if available)
- Return human-readable summary in JSON:
  {{
    "output": "Your order (ORD-1A2B3C4D) has been placed successfully.\nItems:\n- Smart LED TV 55' (2 @ $599.99)\nTotal: $1199.98\n✅ Confirmation email sent to user@example.com"
  }}

---

### Error Handling

- If action fails (invalid SKU, out of stock, empty cart checkout), return a clear message:
  {{
    "output": "❌ Unable to add Smart LED TV 55' to your cart: only 0 units available."
  }}

- Combine multiple errors in a readable sentence separated by periods.

---

### Mandatory Workflow Sequence

1. Run SQL search → validate results → return JSON.
2. Add items to cart → return cart summary → JSON.
3. Remove items (optional) → return cart summary → JSON.
4. Checkout → generate order → save audits → send confirmation email → return order summary → JSON.
5. Always handle errors gracefully → JSON output only.
6. If the user asks about adding another product same steps has to follow 
   example : If user says i want to order data science handboo and air purifier or if the user sayd i want to add another product make sure above 1 to 5 repeat trigger the OrderManagement tool add 
            to cart,show cart should happen never show the output without triggering the tools it handle multiple or sequence order products adding before checkout

---

### Output Rules

- Always return JSON with a single "output" key.
- Never include Python objects, tuples, or raw SQL.
- Output must be **human-readable** and **actionable** for the user.
- Never break JSON formatting (no unterminated strings, no extra characters).

---

### Example Combined Flow

{{
  "output": "✅ Product Found: SKU ELEC-100, Name: Smart LED TV 55' ,Brand: Samsung, Price: 599.99 , Quantity Available: 25 .Do you wanna add to the cart ?"
}}
→ Add to cart →  
{{
  "output": "Added 2 Smart LED TV 55' to your cart. Cart now has: Smart LED TV 55' x 2 = $1199.98"
}}
→ View cart →  
{{
  "output": "Cart items:\n- Smart LED TV 55' x 2 = $1199.98\nTotal: $1199.98\nDo you want to checkout?"
}}
→ Checkout →  
{{
  "output": "Your order (ORD-1A2B3C4D) has been placed successfully.\nItems:\n- Smart LED TV 55' (2 @ $599.99)\nTotal: $1199.98\n✅ Confirmation email sent to user@example.com"
}}

"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", instructions),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}")
    ])
    logger.debug(f"[{session_id}] Prompt created successfully")

    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
    logger.debug(f"[{session_id}] Agent created with {len(tools)} tools")

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=18,
        return_intermediate_steps=True,
    )

    logger.debug(f"[{session_id}] AgentExecutor ready (max_iterations=8)")

    agent_with_memory = RunnableWithMessageHistory(
        runnable=executor,
        get_session_history=get_by_session_id,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    logger.info(f"[{session_id}] Agent with memory wrapper created")
    return agent_with_memory


# ----------------------------------------------------------------------
# Utility: Output Extractor
# ----------------------------------------------------------------------
def extract_output_string(raw_output: str) -> str:
    """
    Extracts only the string inside the "output" key from raw LLM output.
    Works even if JSON is invalid due to unescaped quotes.
    """
    if not raw_output:
        logger.warning("Empty raw output received from LLM.")
        return ""

    cleaned = re.sub(r"^```(?:json)?\n|```$", "", raw_output.strip())

    match = re.search(r'"output"\s*:\s*"(.*)"', cleaned, re.DOTALL)
    if match:
        value = match.group(1).replace('\\"', '"')
        return value

    logger.warning("Could not find 'output' key in LLM response; returning raw cleaned text.")
    return cleaned


# ----------------------------------------------------------------------
# Main Async Order Handler
# ----------------------------------------------------------------------
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def handle_order_placement(session_id: str, user_input: str):
    """
    Main handler for order placement.
    Logs all intermediate reasoning, tool usage, and observations.
    """
    logger.info(f"[{session_id}] 🔹 Starting order placement for input: {user_input[:100]}")

    try:
        # Step 1: Agent creation
        agent = create_order_placement_agent(session_id=session_id)

        # Step 2: LLM Invocation
        logger.info(f"[{session_id}] 🔸 Invoking agent...")
        result = await agent.ainvoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}}
        )

        # Step 3: Log intermediate reasoning steps
        intermediate_steps = result.get("intermediate_steps", [])
        if intermediate_steps:
            logger.info(f"[{session_id}] Agent completed {len(intermediate_steps)} intermediate steps:")
            for i, (action, observation) in enumerate(intermediate_steps, start=1):
                action_type = getattr(action, "tool", "UnknownTool")
                action_input = getattr(action, "tool_input", "")
                logger.info(f"   Step {i}:  Tool → {action_type}")
                logger.debug(f"  Tool Input: {action_input}")
                logger.info(f"  Observation: {observation}")
        else:
            logger.info(f"[{session_id}]  No intermediate steps were returned by the agent.")

        # Step 4: Extract output
        raw_output = result.get("output", "")
        final_output = extract_output_string(raw_output)
        if not final_output.strip():
            final_output = "No output returned by agent."
            logger.warning(f"[{session_id}] Empty output received after extraction.")

        logger.info(f"[{session_id}]  Final Agent Output: {final_output[:250]}")

        return {
            "output": final_output,
            "success": True,
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"[{session_id}]  Error in handle_order_placement: {str(e)}", exc_info=True)
        return {
            "output": f"Error during processing: {str(e)}",
            "success": False,
            "session_id": session_id
        }