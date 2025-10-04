# corrected_schemas.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional




class OrderCancellationInput(BaseModel):

    """
    Schema for cancellatoion of the orders and logs the order and inventory and as well as inventory table and send the cancel confimration
    to the customer    

    Fields:
        order_id: Unique numeric ID of the order from the Order Table.
        
        reason: Customer Cancelled Order Reason
    """

    action: str = Field(..., pattern="^cancel_order$", description="Must be 'cancel_order'")
    order_number: str = Field(..., description="Order NUmber to cancel the order")
    reason: Optional[str] = Field(None, description="Optional reason for cancellation")





































# if __name__ == "__main__":


#     try:
#         ordercancel = OrderCancellationtInput(order_id=1)
#         print(ordercancel.order_id)
#         print(ordercancel.reason)

#         print(f"Validation was sucessful")

#     except Exception as e:

#         print(f"Error while type validation :{str(e)}")






