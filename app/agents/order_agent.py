from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.agents import create_tool_calling_agent, AgentExecutor
from app.agents.memory import get_by_session_id
from app.config.settings import settings

from app.tools.order_tools import (CheckProductExistsTool,
                                   CreateOrderTool,
                                   OrderAuditTool,
                                   InventoryUpdateTool,
                                   SendConfirmationEmailTool)



llm = ChatGoogleGenerativeAI(model=settings.DEFAULT_MODEL,
                             api_key=settings.GEMINI_API_KEY,
                             max_tokens=2000)


tools = [CheckProductExistsTool()]


instructions = "You are an Order Agent responsible for checking the product exist or not "

# Define Prompt Structure 
prompt = ChatPromptTemplate.from_messages([
    ("system", instructions),
    MessagesPlaceholder(variable_name="chat_history"),  
    ("human", "{input}"),
    ("assistant", "I will check the product details."),
    ("placeholder", "{agent_scratchpad}"),
])


agent = create_tool_calling_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True)


agent_with_memory = RunnableWithMessageHistory(
                        runnable=agent_executor,
                        get_session_history=get_by_session_id,
                        input_messages_key="input",
                        history_messages_key="chat_history",
                        output_messages_key="output")


async def handle_order(session_id: str , user_input: str):


    result =  await agent_with_memory.ainvoke({"input": user_input},
                                                config={"configurable": {"session_id": session_id}})
    
    return result
    