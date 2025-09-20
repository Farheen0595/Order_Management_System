from pydantic import BaseModel, Field


class ProductCheckInput(BaseModel):
    
    product_name: str = Field(...,description="Name of the product to check")



class CreateOrderInput(BaseModel):

    product_id: int = Field(...,description="Product ID to order")
    quantity: int = Field(..., description="Number of units to order")
    remarks: str | None = Field(description="Remarks of the Order")



class OrderAuditInput(BaseModel):

    order_id: int
    prev: str
    new: str
    remarks: str


class InventoryUpdateInput(BaseModel):
    product_id: int
    quantity: int
    changeType: str
    remarks: str


class EmailInput(BaseModel):
    to: str
    subject: str
    body: str


    
