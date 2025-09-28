# corrected_schemas.py
from pydantic import BaseModel, Field, EmailStr




class OrderCancellationtInput(BaseModel):

    """
    Schema for cancellatoion of the orders and logs the order and inventory and as well as inventory table and send the cancel confimration
    to the customer    

    Fields:
        order_id: Unique numeric ID of the order from the Order Table.
        
        reason: Customer Cancelled Order Reason
    """

    order_id: int = Field(..., description="Unique Numeric ID for the order from the Orders Table",gt=0)

    reason: str = Field(default="Customer Cancelled the Order", description="Reason for the Cancellation")

    email_address: EmailStr = Field(default="ai_agent05@gmail.com",description="Email of the customer for the order cancellation sent")




# if __name__ == "__main__":


#     try:
#         ordercancel = OrderCancellationtInput(order_id=1)
#         print(ordercancel.order_id)
#         print(ordercancel.reason)

#         print(f"Validation was sucessful")

#     except Exception as e:

#         print(f"Error while type validation :{str(e)}")






