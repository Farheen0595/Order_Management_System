import asyncio
import json
from app.tools.order_placement_tools import OrderPlacementTool
from app.database.engine import engine

async def run_tests():

    tool = OrderPlacementTool()

    try:
        print("\n=== TEST 1: Successful Order ===")

        try:
            result_json = await tool._arun(
                product_id=1,           
                quantity=-2,
                customer_email="student@university.edu",
                remarks="Test order" )
            
            result = json.loads(result_json)
            print("Result:", json.dumps(result, indent=2))

            # Basic checks
            assert result["order"]["product_id"] == 1
            assert result["order"]["quantity"] == 2
            assert result["order"]["status"] == "processed"

            assert result["audit"]["prev_status"] == "processed"
            assert result["audit"]["new_status"] == "shipped"

            assert result["inventory"]["quantityChanged"] == 2
            assert result["inventory"]["changeType"] == "REMOVE"
            assert result["email"]["to"] == "student@university.edu"
            
            print("TEST 1 PASSED")
        except Exception as e:
            print("TEST 1 FAILED:", e)


    finally:
        # Dispose engine once at the very end

        await engine.dispose()
        print("\nDatabase engine disposed.")




if __name__ == "__main__":
    asyncio.run(run_tests())


        # print("\n=== TEST 2: Product Not Found ===")


        # try:
        #     await tool._arun(
        #         product_id=9999,  # Non-existent product
        #         quantity=1,
        #         customer_email="test@test.com"
        #     )
        #     print("❌ TEST 2 FAILED: Expected exception for product not found")


        # except ValueError as e:
        #     print("Caught expected exception:", e)
        #     print("✅ TEST 2 PASSED")


        # except Exception as e:
        #     print("❌ TEST 2 FAILED with unexpected exception:", e)

        # print("\n=== TEST 3: Insufficient Stock ===")



        # try:
        #     await tool._arun(
        #         product_id=1,
        #         quantity=1000,  # More than available stock
        #         customer_email="test@test.com")
        #     print("❌ TEST 3 FAILED: Expected exception for insufficient stock")

        # except ValueError as e:
        #     print("Caught expected exception:", e)
        #     print("✅ TEST 3 PASSED")

        # except Exception as e:
        #     print("❌ TEST 3 FAILED with unexpected exception:", e)



        # print("\n=== TEST 4: Invalid Quantity ===")

        # try:
        #     await tool._arun(
        #         product_id=1,
        #         quantity=0,
        #         customer_email="test@test.com" )
        #     print("❌ TEST 4 FAILED: Expected exception for invalid quantity")

        # except ValueError as e:
        #     print("Caught expected exception:", e)
        #     print("✅ TEST 4 PASSED")

        # except Exception as e:
        #     print("❌ TEST 4 FAILED with unexpected exception:", e)



        # print("\n=== TEST 5: Email Sending Simulation ===")
        # try:
        #     result_json = await tool._arun(
        #         product_id=1,
        #         quantity=1,
        #         customer_email="student@university.edu",
        #         remarks="Email test")
        #     result = json.loads(result_json)
        #     assert result["email"]["success"] is True
        #     print("Email Output:", result["email"])
        #     print("✅ TEST 5 PASSED")


        # except Exception as e:
        #     print("❌ TEST 5 FAILED:", e)
















































# import asyncio
# from app.tools.order_tools import (
#                                    CreateOrderTool,
#                                    OrderAuditTool,
#                                    InventoryUpdateTool,
#                                    SendConfirmationEmailTool)

# from app.database.engine import engine


# ''' EMAIL NOTIFICATION '''
# async def test_create_order_tool():
#     """
#     Test EMAIL NOTIFCATION independently
#     """
#     # Instantiate tool
#     tool = SendConfirmationEmailTool()

#     # Example input parameters
    

#     order_id = 5
#     product_name = "SAMSUNG PRODUCT"
#     to = "sdfarheen05@gmail.com"
#     subject = "order has been placed successful"
#     body = f"{order_id} and {product_name} has been placed and processed"

#     result =  await tool._arun(
#         to=to,
#         subject=subject,
#         body=body
#     )
    
#     await engine.dispose()
#     print("✅ EMAIL NOTIFICATION SEND SUCCESSFULLY:")
    
#     print(result)

# if __name__ == "__main__":
#     asyncio.run(test_create_order_tool())


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



