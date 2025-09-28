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



# Registry of sub-agent

sub_agents = {
                "OrderPlacementAgent": {"handler": handle_order_placement},

                "OrderCancellationAgent" :{"handler": handle_order_cancellation } 
            }
                    


# LLM 
llm = ChatGoogleGenerativeAI( model=settings.DEFAULT_MODEL, api_key=settings.GEMINI_API_KEY,
                                max_tokens=2000,
                                temperature=0,
                                request_timeout=60,  
                            )


# Instructions 

instructions = """
You are the Super Agent.  

Your ONLY output MUST be a **single valid JSON object**.  
Do NOT include any text, explanation, or quotes outside the JSON.  
Do NOT add trailing commas.  

Your job:
1. Read the user input.
2. Determine the MOST relevant sub-agent from the available list.
3. Return ONLY the sub-agent name in JSON.

---

### Available Sub-Agents:

1. OrderPlacementAgent
   - Capabilities:
     - Search inventory using SQL Toolkit.
     - Place customer orders using OrderPlacementTool.
   - Workflow:
     1. Extract brand and product keywords from user input.
     2. Query the `Inventory` table for matching products (status='active').
     3. Return product information (Product Name, Brand, Price, Availability) in human-readable format.
     4. Validate order details if user requests to place an order (quantity, email).
     5. Place the order using `OrderPlacementTool`.
     6. Return structured JSON output:
        {{
          "output": "✅ Your order (ID: <order_id>) for <Product Name> (<quantity> items) has been placed successfully. Total price: $<price>."
        }}
   - Example user queries:
     - "Order 2 Wireless Bluetooth Headphones"
     - "Show me all Samsung products"
     - "I want to order 1 Apple Smartphone X15 for john@email.com"

2. OrderCancellationAgent
   - Capabilities:
     - Check if an order exists using SQL Toolkit.
     - Cancel an order using `OrderCancellationTool`.
   - Workflow:
     1. Extract `order_id` from user input.
     2. Query the `Orders` table to validate the order exists.
        - If invalid:
          {{ "output": "❌ Invalid order ID. Please provide a valid order ID." }}
     3. Return order details for confirmation:
        {{ "output": "📦 Order found! Order ID: <order_id>, Status: <status>, Quantity: <quantity>. Do you want to cancel this order?" }}
     4. If user confirms **yes**:
        - Trigger `OrderCancellationTool` with:
          - `order_id` (from input)
          - `reason` (default = "Customer Cancelled the Order" if missing)
          - `email_address` (default = aiagent_05@gmail.com if missing)
        - Tool performs:
          - Update **Order Table** (status = Cancelled, quantity = 0)
          - Insert record into **Order Audit**
          - Restore stock in **Inventory** and log in **Inventory Audit**
          - Send cancellation confirmation email
          - Calculate `total_refund` = ordered_quantity × price
        - Return structured JSON:
          {{
            "order": {{
              "order_id": <order_id>,
              "status": "Cancelled"
            }},
            "product_name": "<product_name>",
            "email": {{"to": "<customer_email>"}},
            "total_refund": <refund_amount>
          }}
        - Convert to human-readable output:
          {{ "output": "✅ Your order no #<order_id> has been cancelled successfully. A refund of <refund_amount> will be credited within 5 working days. 💳" }}
     5. If user says **no** → reply politely:
        {{ "output": "🙏 Okay, no cancellation made. Do you need any other assistance?" }}
   - Example user queries:
     - "Cancel my order #5"
     - "I want to cancel order 12 for john@example.com"
     - "Check order ID 15"
     - "Yes, cancel my order"
     - "No, keep my order"

---

### General Rules for Master Agent
- Always respond with **a single valid JSON object**:
  {{
    "sub_agent": "<AgentName>"
  }}
- Never output raw SQL or tool JSON to the user.
- Always maintain polite and professional tone with emojis.
- Determine the correct sub-agent by interpreting user intent:
  - Product search or order placement → `OrderPlacementAgent`
  - Order cancellation or checking order status → `OrderCancellationAgent`
- Use `OrderPlacementAgent` and `OrderCancellationAgent` **handlers** defined in the `sub_agents` registry.
- Extract and return JSON cleanly so downstream code can parse it safely.

---

### JSON Output Format (Mandatory)
- Always return:
  {{
    "sub_agent": "<AgentName>"
  }}
- No additional text, no quotes outside JSON, no explanations.
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
async def master(user_input: str,session_id: str):
    try:
        # Invoke master agent to select the sub-agent
        resp = await master_agent.ainvoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}}
        )
        print("Sub-agent selection:", resp.content)

        # Extract JSON safely
        data = extract_json(resp.content)
        if not data:
            return {"ok": False, "error": "Failed to extract JSON", "raw": resp.content}

        sub_agent_name = data.get("sub_agent")
        agent_entry = sub_agents.get(sub_agent_name)
        if not agent_entry:
            return {"ok": False, "error": f"Unsupported sub-agent: {sub_agent_name}", "raw": data}

        # Call the sub-agent handler with try/except
        try:
            sub_result = await agent_entry["handler"](session_id, user_input=user_input)

        except Exception as e:
            print("Sub-agent error:", traceback.format_exc())
            sub_result = {
                "output": f"Error in {sub_agent_name}: {str(e)}",
                "success": False,
                "session_id": session_id}

        print("Result from sub_agent:", sub_result)


        # Safely parse output if it's a stringified dict
        final_output = ""
        if isinstance(sub_result.get("output"), str):
            try:
                nested_output = ast.literal_eval(sub_result["output"])
                final_output = nested_output.get("output") or nested_output.get("message") or sub_result["output"]
            except Exception:
                final_output = sub_result["output"]
        else:
            final_output = sub_result.get("output", "")

        return {
            "output": final_output,
            "success": sub_result.get("success", False),
            "session_id": sub_result.get("session_id", session_id),
        }

    except Exception as e:
        print("Master agent error:", traceback.format_exc())
        return {
            "output": f"Unexpected error in master agent: {str(e)}",
            "success": False,
            "session_id": session_id
        }

 