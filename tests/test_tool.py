import asyncio
from app.tools.order_tools import (
                                   CreateOrderTool,
                                   OrderAuditTool,
                                   InventoryUpdateTool,
                                   SendConfirmationEmailTool)

from app.database.engine import engine


''' EMAIL NOTIFICATION '''
async def test_create_order_tool():
    """
    Test EMAIL NOTIFCATION independently
    """
    # Instantiate tool
    tool = SendConfirmationEmailTool()

    # Example input parameters
    

    order_id = 5
    product_name = "SAMSUNG PRODUCT"
    to = "sdfarheen05@gmail.com"
    subject = "order has been placed successful"
    body = f"{order_id} and {product_name} has been placed and processed"

    result =  await tool._arun(
        to=to,
        subject=subject,
        body=body
    )
    
    await engine.dispose()
    print("✅ EMAIL NOTIFICATION SEND SUCCESSFULLY:")
    
    print(result)

if __name__ == "__main__":
    asyncio.run(test_create_order_tool())


# ''' INVENTORY AUDIT TABLE '''
# async def test_create_order_tool():
#     """
#     Test CreateOrderTool independently
#     """
#     # Instantiate tool
#     tool = InventoryUpdateTool()

#     # Example input parameters

#     product_id = 4
#     quantity_available = 4
#     changeType = "REMOVE",
#     quantityChanged  = -2
#     remarks = "Product purchased"

#     result =  await tool._arun(product_id=product_id,
#                                                 quantity_available=quantity_available,
#                                                 changeType=changeType,
#                                                 quantityChanged=quantityChanged,
#                                                 remarks=remarks)
    
#     await engine.dispose()
#     print("✅ CreateOrder Audit ToolTest Result:")
#     print(result)

# if __name__ == "__main__":
#     asyncio.run(test_create_order_tool())




# ''' ORDER AUDIT TABLE '''
# async def test_create_order_tool():
#     """
#     Test CreateOrderTool independently
#     """
#     # Instantiate tool
#     tool = OrderAuditTool()

#     # Example input parameters
#     order_id=5,
#     prev_status="PROCESSED", 
#     new_status="SHIPPED", 
#     remarks="Test Order"

#     # Run the async tool
#     result = await tool._arun(
#         order_id=order_id,
#         prev_status=prev_status,
#         new_status=new_status,
#         remarks=remarks
#     )

#     await engine.dispose()
#     print("✅ CreateOrder Audit ToolTest Result:")
#     print(result)

# if __name__ == "__main__":
#     asyncio.run(test_create_order_tool())




# ''' ORDER CREATED SCRIPT'''

# async def test_create_order_tool():
#     """
#     Test CreateOrderTool independently
#     """
#     # Instantiate tool
#     tool = CreateOrderTool()

#     # Example input parameters
#     product_id = 1        # Replace with a valid product_id from your Inventory table
#     quantity = 2
#     remarks = "Test Order"
#     status = "PROCESSED"

#     # Run the async tool
#     result = await tool._arun(
#         product_id=product_id,
#         quantity=quantity,
#         status=status,
#         remarks=remarks
#     )

#     await engine.dispose()
#     print("✅ CreateOrderTool Test Result:")
#     print(result)

# if __name__ == "__main__":
#     asyncio.run(test_create_order_tool())



