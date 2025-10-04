from app.tools.product_inquiry_tools import ProductVectorSearchTool
import asyncio, json

async def run_test():
    tool = ProductVectorSearchTool()
    result = await tool._arun("Which products have Wi-Fi under 600 USD?")
    data = json.loads(result)

    if data["success"]:
        print("✅ Test Passed")
    else:
        print("❌ Test Failed")

    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    asyncio.run(run_test())
