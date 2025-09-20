from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional,Annotated,Type

from app.database.models import (Inventory ,
                                 InventoryAudit,
                                 Order,
                                 OrderAudit)

from app.database.engine import AsyncSessionLocal
from app.services.inventory_service import product_exists,update_inventory
from app.services.order_service import create_order
from app.services.audit_service import order_audit
from app.services.email_service import send_email

from app.schemas.order import (ProductCheckInput,
                               CreateOrderInput,
                               OrderAuditInput,
                               InventoryUpdateInput,
                               EmailInput)


class CheckProductExistsTool(BaseTool):

    name:str = "check_product_existence"
    description:str = "Check if a product exists in inventory by name"
    args_schema: Type[BaseModel] = ProductCheckInput
    return_direct:bool = True
    
    async def _arun(self, product_name: str):
        
        async with AsyncSessionLocal() as db:

            records,flag = await product_exists(db ,product_name)

            if flag:
                return f'The product {product_name} exits'
            else:
                return f'The product {product_name} is not available'
        
    def _run(self, *args, **kwargs):
        raise NotImplementedError("Sync model not supported")
    


class CreateOrderTool(BaseTool):

    name: str = "create _order"
    description: str = "Create a new order in the Order Table"
    args_schema: Type[BaseModel] = CreateOrderInput
    return_direct: bool = True

    async def _arun(self, product_id: int,
                    quantity: int,
                    remarks: str = "Ordered"):

        async with AsyncSessionLocal() as db:

            async with db.begin():

                order = await create_order(db, product_id,quantity,remarks)

                return {"order_id":order.order_id,
                        "status":order.status,
                        "remarks":order.remarks,
                        "orderDate":str(order.orderDate)}
            

    def _run(self, *args, **kwargs):
        return NotImplementedError("Sync not supported")
    


class OrderAuditTool(BaseTool):

    name:str = "order_audit"
    description:str  = "Log an audit entry for an order"
    args_schema: Type[BaseModel] = OrderAuditInput

    async def _arun(self, order_id: int,
                    prev: str, 
                    new: str, 
                    remarks: str):
        
        async with AsyncSessionLocal() as db:

            async with db.begin():

                await order_audit(db, order_id, prev, new, remarks)

                return f"Audit logged for order {order_id}"
            
    def _run(self, *args, **kwargs):
        
        return NotImplementedError("Sync not supported")




class InventoryUpdateTool(BaseTool):

    name:str = "update_inventory"
    description:str = """Deduct or Update from inventory table and update it in quantity available  \
                        and original quantity and removed or added will be updated"""
    args_schema: Type[BaseModel] = InventoryUpdateInput

    async def _arun(self, 
                    product_id: int,
                    quantity: int, 
                    changeType: str,
                    remarks: str):
        
        async with AsyncSessionLocal() as db:

            async with db.begin():

                inv = await update_inventory(db, product_id, quantity, changeType, remarks)

                return f"Inventory updated for product {product_id}, remaining {inv.quantity_available}"
            
    def _run(self, *args, **kwargs): 

        return NotImplementedError("Sync not supported")



class SendConfirmationEmailTool(BaseTool):

    name:str = "send_email"
    description:str = "Send order confirmation email"
    args_schema:str = EmailInput

    async def _arun(self, to: str, subject: str, body: str):

        return await send_email(to, subject, body)
    
    def _run(self, *args, **kwargs): 
        raise NotImplementedError("Sync not supported")




