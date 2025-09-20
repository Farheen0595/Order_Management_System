import asyncio
from app.agents.master_agent import master



async def main():

    session_id = "test_master"

    res1 = await master(session_id,"Does a Mobile Phone Exists?")

    print("First:", res1)

    res2 =  await master(session_id, "What about the Laptop ?")

    print(f"Second: {res2}")




if __name__ == "__main__":


    asyncio.run(main())