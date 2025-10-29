# test_master_agent.py
import asyncio
from app.agents.master_agent import master
import json

# === Example Usage & Testing ===
async def main():
    """Test the super agent with dynamic selection (currently order-focused)"""
    
    test_queries = [
        # "Order 2 wireless headphones",           # ORDER_AGENT
        # "Order 2 wireless headphones",          # ORDER_AGENT  I 
        # "can show me the apple products ?",
        # "i want to order smartphone x15",
        # "I accidentally placed order 25, cancel it",
        "Order ID 50 should be cancelled"

    ]
    
    print("Testing Super Agent with Dynamic Selection:")
    print("="*60)
    print("NOTE: Currently all agents route through ORDER_AGENT")
    print("Framework ready for future agent implementations")
    print("="*60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Query: '{query}'")
        print("-" * 40)
        
        result = await master("test_session", query)
        
        # Extract agent info
        output = result.get("output", "{}")
        print("Final Output:", output)  # <-- print instead of return

if __name__ == "__main__":
    asyncio.run(main())
