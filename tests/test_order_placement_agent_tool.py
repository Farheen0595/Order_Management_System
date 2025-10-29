import asyncio
import json
from app.tools.order_placement_tools import OrderPlacementTool
from app.database.engine import engine


# Static session & SKU for test
TEST_SESSION_ID = "1ecb477e-d9e3-4e30-ae12-ad9ed1501899"
TEST_SKU_EXISTING = "ELEC-1003"   # should exist in your Inventory table
TEST_SKU_INVALID = "INVALID-0000" # non-existent SKU


# async def test_add_to_cart_valid():
#     tool = OrderPlacementTool(session_token=TEST_SESSION_ID)
#     print("\n=== TEST 1: ADD VALID ITEM TO CART ===")
#     result = await tool._arun(action="add_to_cart", sku=TEST_SKU_EXISTING, quantity=2)
#     print(result)


# async def test_add_to_cart_invalid():
#     tool = OrderPlacementTool(session_token=TEST_SESSION_ID)
#     print("\n=== TEST 2: ADD INVALID SKU ===")
#     result = await tool._arun(action="add_to_cart", sku=TEST_SKU_INVALID, quantity=1)
#     print(result)


# async def test_view_cart():
#     tool = OrderPlacementTool(session_token=TEST_SESSION_ID)
#     print("\n=== TEST 3: VIEW CART ===")
#     result = await tool._arun(action="view_cart")
#     print(result)


# async def test_remove_from_cart():
#     tool = OrderPlacementTool(session_token=TEST_SESSION_ID)
#     print("\n=== TEST 4: REMOVE FROM CART ===")
#     result = await tool._arun(action="remove_from_cart", sku=TEST_SKU_EXISTING, quantity=1)
#     print(result)


# async def test_checkout():
#     tool = OrderPlacementTool(session_token=TEST_SESSION_ID)
#     print("\n=== TEST 5: CHECKOUT ===")
#     result = await tool._arun(action="checkout")
#     print(result)


# async def test_view_after_checkout():
#     tool = OrderPlacementTool(session_token=TEST_SESSION_ID)
#     print("\n=== TEST 6: VIEW CART AFTER CHECKOUT ===")
#     result = await tool._arun(action="view_cart")
#     print(result)


# async def test_empty_checkout():
#     tool = OrderPlacementTool(session_token="empty-cart-session")
#     print("\n=== TEST 7: CHECKOUT EMPTY CART ===")
#     result = await tool._arun(action="checkout")
#     print(result)


async def run_all_tests():
    try:
        # await test_add_to_cart_valid()
        # await test_add_to_cart_invalid()
        await test_view_cart()
        # await test_remove_from_cart()
        # await test_checkout()
        # await test_view_after_checkout()
        # await test_empty_checkout()

    finally:
        await engine.dispose()
        print("\n✅ Database engine disposed.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
