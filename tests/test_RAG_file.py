# main.py

from app.agents.product_inquiry_agent import RAGRunner
import asyncio


async def run_example():
    rag = RAGRunner(query_func="Get the details of the Data Science Hand Book")

    result = await rag.run(
        session_id="user123",
        query="Tell me about smart TVs",
        collection="product-inquriy",
        k=5,
    )

    print(result)

asyncio.run(run_example())
