# tests/test_product_inquiry_agent.py
import asyncio
import json
from datetime import datetime
from app.agents.product_inquiry_agent_1 import handle_product_inquiry


async def test_product_inquiry_agent():
    # Realistic product inquiry test cases
    test_cases = [
        # "Show me products under 600 USD with Wi-Fi",
        # "Does Apple Smartphone X15 exist?",
        # "List all Bluetooth headphones",
        # "Find Dell laptops",
        # "Show me all Nike products",
        # "Do you have air purifiers?",
        # "Find jackets for women",
        # "What books are available?",
        "Any robot vacuum cleaners?",
        "Smart TV Samsung details"
    ]

    results = []

    for i, query in enumerate(test_cases, 1):
        print(f"\n{i} TEST: {query}")
        try:
            result = await handle_product_inquiry("test_session", query)

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
    with open("product_inquiry_test_results.json", "w") as f:
        json.dump(results, f, indent=4)

    print("\n📝 Test results saved to product_inquiry_test_results.json")


if __name__ == "__main__":
    asyncio.run(test_product_inquiry_agent())
