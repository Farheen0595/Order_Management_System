from pydantic import BaseModel, Field, EmailStr,field_validator
from typing import Optional, List, Dict, Any,Literal




class OrderPlacementInput(BaseModel):

    action: Literal["add_to_cart", "remove_from_cart", "view_cart", "checkout"] = Field(..., description="Cart or order action to perform")
    sku: Optional[str] = Field(None, description="SKU required for add/remove")
    quantity: Optional[int] = Field(None, description="Quantity for add/remove (defaults to 1)")
    customer_email: Optional[EmailStr] = Field(default="sdfarheen05@gmail.com", 
                                               description="Email used at checkout")

    @field_validator("quantity", mode="before")
    def validate_quantity(cls, v):
        if v is None:
            return 1
        
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        
        return v