# tests/test_order_cancellation_tool.py

import asyncio
from app.tools.order_cancellation_tools import OrderCancellationTool


async def run_tests():
    tool = OrderCancellationTool()

    # ---- Test 1 ----
    print("\n--- Test 1: Cancel non-existent order ---")
    result = await tool._arun(
        action="cancel_order",
        order_number="ORD-NOTEXIST",  # guaranteed not to exist
        reason="Testing invalid order"
    )
    print("Result:", result)

    # ---- Test 2 ----
    print("\n--- Test 2: Cancel valid single-row order ---")
    # Use an actual order_number from your DB that has only one row (e.g. BOOK-5001)
    result = await tool._arun(
        action="cancel_order",
        order_number="ORD-1289BDBD",  # replace with your real single-row order_number
        reason="Customer requested cancellation"
    )
    print("Result:", result)

    # ---- Test 3 ----
    print("\n--- Test 3: Cancel valid multi-row order ---")
    # Use an order_number that exists with multiple rows (e.g. COMP-3001 + ELEC-1002 same order_number)
    result = await tool._arun(
        action="cancel_order",
        order_number="ORD-1289BDBD",  # replace with your real multi-row order_number
        reason="Customer cancelled full order"
    )
    print("Result:", result)


if __name__ == "__main__":
    asyncio.run(run_tests())
