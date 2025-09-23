# corrected_schemas.py
from pydantic import BaseModel, Field, EmailStr

class CreateOrderInput(BaseModel):

    """
    Schema for creating a new order record in the orders table.
    
    This tool creates an order entry linking a product to a customer purchase request.
    The order will be created with 'pending' status and can be tracked through the order lifecycle.
    """

    product_id: int = Field(..., description="Unique numeric identifier of the product from Inventory table (NOT the SKU). "
                                            "Extract this from SQL query results as the first column (integer).")
    

    quantity: int = Field(..., gt=0, description="Number of units customer wants to purchase. Must be positive integer "
                      "and should not exceed available inventory quantity.")
    
    status: str = Field(default="pending", description="Current status of the order. Use 'pending' for new orders. " 
                           "Other values: 'confirmed'.")
    
    remarks: str = Field(default="Order placed",  description="Optional notes about the order such as 'Customer order'")



class OrderAuditInput(BaseModel):

    """
    Schema for logging order status changes and audit.
    
    This tool creates an audit record every time an order status changes,
    providing complete traceability of order lifecycle events.
    """

    order_id: int = Field(..., description="Unique identifier of the order being audited. "
                   "Get this from the create_order tool result (order_id field)." )
    prev_status: str = Field(..., description="Previous status before the change. For new orders, use 'none'. "
                                     "For existing orders, use current status like 'pending', 'confirmed', etc.")
    

    new_status: str = Field(..., description="New status after the change. Typically 'pending' for new orders, " "'confirmed' for approved orders, 'shipped' for dispatched orders.")

    remarks: str = Field(default="Order status updated",  description="Descriptive note about why status changed. Examples: "
                   "'Order created successfully', 'Payment confirmed', 'Shipped via FedEx'.")



class InventoryUpdateInput(BaseModel):

    """
    Schema for updating inventory quantities and logging inventory audit trail.
    
    This tool reduces inventory when orders are placed and creates an audit record
    of the inventory change for tracking purposes.
    """
    product_id: int = Field(..., description="Unique numeric identifier of the product whose inventory is being updated. ""Must match the product_id used in create_order tool.")
    changeType: str = Field(..., 
        description="Type of inventory change being made. Use 'REMOVE' for order deductions "
                   "or 'ADD' for inventory restocking. For orders, always use 'REMOVE'.")
    
    quantityChanged: int = Field(..., description="Number of units being added or removed from inventory. "
                   "For orders, this should match the order quantity (positive number).")
    

    remarks: str = Field(default="Inventory deduction for order", description="Descriptive note about the inventory change. Include order reference "
                   "like 'Order #12345 inventory deduction' or 'Restock from supplier'.")


class EmailInput(BaseModel):
    """
    Schema for sending order confirmation emails to customers.
    
    This tool sends a formatted email confirmation with order details,
    pricing information, and next steps to the customer.
    """

    to: EmailStr = Field(..., 
        description="Customer's email address where confirmation should be sent. "
                   "Must be valid email format like 'customer@example.com'.")
    
    subject: str = Field(..., 
        description="Email subject line. Should include order reference like "
                   "'Order Confirmation #12345' or 'Your Samsung TV Order Confirmation'.")
    
    body: str = Field(..., description="Complete email body with order details including: "
                   "product name, quantity, unit price, total amount, order ID, "
                   "expected delivery time, and thank you message."
    )

