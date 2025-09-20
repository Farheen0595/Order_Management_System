import asyncio
from app.tools.order_tools import (CheckProductExistsTool,
                                   CreateOrderTool,
                                   OrderAuditTool,
                                   InventoryUpdateTool,
                                   SendConfirmationEmailTool)

from app.database.engine import engine


async def main():

    tool = SendConfirmationEmailTool()

    result = await tool._arun(
        to="sdfarheen05@gmail.com",
        subject="Order Confirmation",
        body="Your order is confirmed!" )
    print("✅ SendConfirmationEmailTool:", result)


if __name__ == "__main__":
    
    asyncio.run(main())


# ''' INSERT THE LOGS AND UPDATE IN THE INVENTORY'''
# async def main():

#     tool = InventoryUpdateTool()

#     # Use an existing product_id from Inventory table

#     result = await tool._arun(product_id=3, quantity=1,changeType="REMOVE",remarks="deducted stock for test")

#     print("✅ InventoryUpdateTool:", result)

#     await engine.dispose()



# ''' ORDER AUDIT TABLE '''

# async def main():

#     tool = OrderAuditTool()

#     # Use an existing order_id from Orders table

#     result = await tool._arun(order_id=3, prev="PROCESSED", new="SHIPPED", remarks="Test Order")

#     print("✅ OrderAuditTool:", result)

#     await engine.dispose()






# ''' ORDER CREATED SCRIPT'''
# async def main():

#     tool  = CreateOrderTool()

#     result = await tool._arun(product_id=1,quantity=2,remarks="Test Order")

#     print(" ORDER CREATED SUCCESSFULLY :",result)

#     await engine.dispose()


''' PRODUCT CHECK TOOL SCRIPT'''
# async def main():

#     tool = CheckProductExistsTool()

#     product_name = "Smart LED TV 55"

#     print(f" Checking if {product_name} exists ...")

#     result  = await tool.arun(product_name)


#     if result:
#         print(f"Results the products:{result}")
#         print(f"product_name: {result.product_name} and Available Quantity: {result.quantity_available} and price:{result.price}")
#         print(f"Product {product_name} exists in inventory")
#     else:

#         print(f"Product {product_name} does not exist")

#     await engine.dispose()


# async def test_check_product_exists():
#     tool = CheckProductExistsTool()
#     result = await tool._arun(product_name="Mobile Phone")
#     print("✅ CheckProductExistsTool:", result)


# async def test_create_order():
#     tool = CreateOrderTool()
#     # Use an existing product_id from your Inventory table
#     result = await tool._arun(product_id=1, quantity=2, remarks="Test order")
#     print("✅ CreateOrderTool:", result)


# async def test_log_order_audit():
#     tool = OrderAuditTool()
#     # Use an existing order_id from Orders table
#     result = await tool._arun(order_id=1, prev="PROCESSED", new="SHIPPED", remarks="sent out")
#     print("✅ OrderAuditTool:", result)


# async def test_update_inventory():
#     tool = InventoryUpdateTool()
#     # Use an existing product_id from Inventory table
#     result = await tool._arun(product_id=1, quantity=1, remarks="deducted stock for test")
#     print("✅ InventoryUpdateTool:", result)


# async def test_send_email():
#     tool = SendConfirmationEmailTool()
#     result = await tool._arun(
#         to="test@example.com",
#         subject="Order Confirmation",
#         body="Your order is confirmed!"
#     )
#     print("✅ SendConfirmationEmailTool:", result)


# async def main():
#     print("----- Running Tool Tests -----")
#     await test_check_product_exists()
#     await test_create_order()
#     await test_log_order_audit()
#     await test_update_inventory()
#     await test_send_email()


# if __name__ == "__main__":
#     asyncio.run(main())


