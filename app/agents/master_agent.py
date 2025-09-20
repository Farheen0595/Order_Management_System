import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from app.config.settings import settings
from app.agents.memory import get_by_session_id
from app.agents.order_agent import handle_order



llm = ChatGoogleGenerativeAI(
    model=settings.DEFAULT_MODEL,
    api_key=settings.GEMINI_API_KEY,
    max_tokens=2000
)


instructions = """
You are the master Agent.
Your ONLY output MUST be valid JSON.
Do NOT include explanations, comments, or any text outside JSON.
Return EXACTLY in this format:
<json_start> 
{{"intent": "CHECK_PRODUCT", "fields": {{"product_name": "<name>"}}}}
<json_end>
"""


prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(instructions),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    ("assistant", "I will check"),
    ("placeholder", "{agent_scratchpad}"),
])



chain = prompt | llm

master_agent = RunnableWithMessageHistory(
    runnable=chain,
    get_session_history=get_by_session_id,
    input_messages_key="input",
    history_messages_key="chat_history",
    output_messages_key="output",
)


async def master(session_id: str, user_input: str):
   
    resp = await master_agent.ainvoke(
        {"input": user_input},
        config={"configurable": {"session_id": session_id}}
    )

    print("DATA BODY",resp.content)

    try:
        data = json.loads(resp.content)
    except Exception as e:
        return {"ok": False, "error": f"JSON parsing failed: {e}"}

    if (data.get("intent") or "").upper() == "CHECK_PRODUCT":

        product_name = data["fields"]["product_name"]
        result = await handle_order(session_id, f"Check if {product_name} exists")
        return {
            "ok": True,
            "intent": "CHECK_PRODUCT",
            "product": product_name,
            "result": result,
        }

    return {"ok": False, "error": f"Unsupported intent: {data}"}
