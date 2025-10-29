# test_agent_simple.py
import asyncio
from app.agents.order_placement_agent import handle_order_placement



async def test_order_placement_agent():

    
    # test_cases = [
    #     "Order 2 Wireless Bluetooth Headphones for mary@samsung.com"

    # ]

    test_cases = [
        # "Does Samsung Smart LED TV exist?",
        # "Order 2 wireless headphones",
        # "Order 1 Apple Smartphone X15 for john@email.com",
        # "Can you place Order 1 Apple Smartphone X15 for john@email.com ?",
         "Can you Order 2 Samsung Smart LED TVs for mary@samsung.com",
        # "i want to order smartphone x15",
        # "Order 2 Wireless Bluetooth Headphones for mary@samsung.com"
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
    asyncio.run(test_order_placement_agent())
