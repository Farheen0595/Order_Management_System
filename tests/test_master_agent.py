# test_master_agent.py
import asyncio
from app.agents.master_agent import master

async def run_test():
    session_id = "test-session-001"
    user_input = "Order Data Science Handbook for student@university.edu"

    result = await master(session_id, user_input)

    print("\n=== MASTER AGENT TEST ===")
    print("Input :", user_input)
    print("Output:", result)
    print("=========================\n")

if __name__ == "__main__":
    asyncio.run(run_test())
