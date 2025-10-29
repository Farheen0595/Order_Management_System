# test_agent_simple.py
import asyncio
import json
from datetime import datetime
from app.agents.order_cancellation_agent import handle_order_cancellation


async def test_order_cancellation_agent():
    # Realistic cancellation-focused test cases
    test_cases = [
        # "Cancel my order #5",
        # "I want to cancel order 12",
        # "Can you cancel my order with id 20?",
        # "Please cancel order 15 for me",
        # "I accidentally placed order 25, cancel it",
        # "Cancel order 30 because I changed my mind",
        # "Order ID 50 should be cancelled",
        # "Cancel order 75 for john@example.com",
        # "Cancel my last order",   # edge case: vague query
        # "Can you cancel order number 100 and refund me?",  # refund emphasis
    ]

    results = []

    for i, query in enumerate(test_cases, 1):
        print(f"\n{i} TEST: {query}")
        try:
            result = await handle_order_cancellation("test_session", query)

            status = "PASSED" if result.get("success") else "FAILED"
            print(f"{status} | Output: {result.get('output', '')[:200]}")

            # Append structured result for logging
            results.append({
                "test_case": query,
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "response": result
            })
        except Exception as e:
            print(f"FAILED with exception: {e}")
            results.append({
                "test_case": query,
                "timestamp": datetime.now().isoformat(),
                "status": "EXCEPTION",
                "error": str(e)
            })

    # Save results into JSON for future reference
    with open("cancellation_test_results.json", "w") as f:
        json.dump(results, f, indent=4)

    print("\n📝 Test results saved to cancellation_test_results.json")


if __name__ == "__main__":
    asyncio.run(test_order_cancellation_agent())
