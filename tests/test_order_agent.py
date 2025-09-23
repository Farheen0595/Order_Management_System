# test_agent_simple.py
import asyncio
from app.agents.order_agent import handle_order_placement



async def test_order_agent():


    test_cases = [
        # "Does Samsung Smart LED TV exist?",
        # "Show me all Apple products",
        # "Order 1 Apple Smartphone X15 for john@email.com",
        "Order 2 Samsung Smart LED TVs for mary@samsung.com",
        # "Order Data Science Handbook for student@university.edu"
    ]
    
    for i, query in enumerate(test_cases, 1):
        print(f"\n{i} TEST: {query}")
        try:
            result = await handle_order_placement("test_session", query)
            status = "PASSED" if result['success'] else "FAILED"
            print(f"{status} | Output: {result['output'][:200]}")
        except Exception as e:
            print(f"FAILED with exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_order_agent())
