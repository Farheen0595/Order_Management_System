import asyncio
from app.agents.order_agent import handle_order




async def main():

    session_id = "test_order"

    # First Query

    res1 = await handle_order(session_id,
                              "Check if Phone Exists")
    
    print(f"results of the first question - {res1}")

    # Second Query

    res2 = await handle_order(session_id,
                              "What about Laptop")
    
    print(f"resulst of the seconf question - {res2}")
    

if __name__ == "__main__":


    asyncio.run(main())