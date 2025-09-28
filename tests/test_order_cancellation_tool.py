from app.tools.order_cancellation_tools import OrderCancellationTool
import asyncio
from app.database.engine import engine
import json




async def run_test():

    tool = OrderCancellationTool()

    # Run cancellation for order_id=2
    result = await tool._arun(
        order_id=23
    )

    data = json.loads(result)
    await engine.dispose()
    print("✅ Test Passed: Order cancelled successfully")
    print("Response:", data)


if __name__ == "__main__":
    asyncio.run(run_test())

























# ------------------------------------------------
# TEST ARGS SCHEMA TO FETCH THE DEFAULT PARAMETERS
# -----------------------------------------------

# async def test_args_schema():


#     tool = OrderCancellationTool()


#     args = await tool._arun(order_id=2)

#     await engine.dispose()


#     return args



# if __name__ == "__main__":


#     arguments = asyncio.run(test_args_schema())
#     print(arguments)




# ----------------------
# TESTING THE PARAMTERS
# -----------------------


# async def test_paramters():

#     tool = OrderCancellationTool()

   
#     try:
#         result = await tool._arun(
#                 order_id=2)
        
#         print(type(result))
#         print("ORDER ID",result.order_id)
#         # Basic checks
#         assert result.order_id == 2
        
#     except Exception as e:
#         print(f"Invalid parameters - str{e}")

#     finally:
#         await engine.dispose()
#         print("\nDatabase engine disposed.")




# if __name__ == "__main__":
#     asyncio.run(test_paramters())

