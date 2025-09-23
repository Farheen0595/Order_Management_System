from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional,Annotated,Type
from sqlalchemy import text
import json

from app.database.models import (Inventory ,
                                 InventoryAudit,
                                 Order,
                                 OrderAudit)

from app.database.engine import AsyncSessionLocal

from app.schemas.order import (
                               CreateOrderInput,
                               OrderAuditInput,
                               InventoryUpdateInput,
                               EmailInput) 



# ----------------------------
#  Order Table Create Tool
# ----------------------------

class CreateOrderTool(BaseTool):
    name: str = "create_order"
    description: str = "Create a new order in the Orders table"
    args_schema: Type[BaseModel] = CreateOrderInput
    return_direct: bool = True

    async def _arun(self, product_id: int, quantity: int, status: str, remarks: str = "Ordered"):

        """
        Create a new order for the new parameters.
        """

        async with AsyncSessionLocal() as db:
            async with db.begin():  
               
                order = Order(
                    product_id=product_id,
                    quantity=quantity,
                    status=status,
                    remarks=remarks
                )

                db.add(order)         
                await db.flush()      
                await db.refresh(order)  

            
                output = {
                    "order_id": order.order_id,
                    "product_id": order.product_id,
                    "quantity": order.quantity,
                    "status": order.status,
                    "remarks": order.remarks}
                
                return json.dumps(output)
    
    def _run(self, *args, **kwargs):
        raise NotImplementedError("Sync execution not supported, use _arun.")




# ----------------------------
# Order Audit Tool
# ----------------------------

class OrderAuditTool(BaseTool):
    name: str = "order_audit"
    description: str = "Log an audit entry for an order"
    args_schema: Type[BaseModel] = OrderAuditInput
    return_direct: bool = True

    async def _arun(self, order_id: int, prev_status: str, new_status: str, remarks: str = "Order placed"):
        async with AsyncSessionLocal() as db:
            async with db.begin():
                

                orderAudit = OrderAudit(order_id=order_id, 
                                        previousStatus=prev_status, 
                                        newStatus=new_status,
                                        remarks=remarks)

                db.add(orderAudit)
                await db.flush()      
                await db.refresh(orderAudit) 

                output = {
                        "order_id":orderAudit.order_id,
                        "prev_status":orderAudit.previousStatus,
                        "new_status":orderAudit.newStatus,
                        "remarks":orderAudit.remarks}
                
                return json.dumps(output)
    

    def _run(self, *args, **kwargs):
        raise NotImplementedError("Sync not supported")



# ----------------------------
# Inventory Update Tool
# ----------------------------
class InventoryUpdateTool(BaseTool):
    name: str = "update_inventory"
    description: str = "Deduct or update inventory and log audit"
    args_schema: Type[BaseModel] = InventoryUpdateInput
    return_direct: bool = True

    async def _arun(self, product_id: int, changeType:str, quantityChanged:int, remarks: str = "Inventory deduction"):
        async with AsyncSessionLocal() as db:
            async with db.begin():

                inv = await db.get(Inventory,product_id)

                if not inv:
                    raise ValueError("Product not found")
                
                quantity_available = inv.quantity_available

                if changeType.upper() == "REMOVE":

                    if inv.quantity_available < quantityChanged:

                        raise ValueError("Insufficient Stock")
                    else:
                        
                        inv.quantity_available -= quantityChanged

           

                else:
                    raise ValueError(f"Invalid changeType: {changeType}")
                
                
                inventoryAudit = InventoryAudit(product_id=product_id,
                                                quantity_available=quantity_available,
                                                changeType=changeType,
                                                quantityChanged=quantityChanged,
                                                remarks=remarks)



                db.add(inventoryAudit)
                await db.flush()    
                await db.refresh(inv)   
                await db.refresh(inventoryAudit) 
                await db.commit()

                output = {
                        "product_id":inventoryAudit.product_id,
                        "quantity_available":inventoryAudit.quantity_available,
                        "changeType":inventoryAudit.changeType,
                        "quantityChanged":inventoryAudit.quantityChanged,
                        "remarks":inventoryAudit.remarks}
                

                return json.dumps(output)
    
    def _run(self, *args, **kwargs):
        raise NotImplementedError("Sync not supported")


# ----------------------------
# Send Email Tool
# ----------------------------

class SendConfirmationEmailTool(BaseTool):
    name: str = "send_email"
    description: str = "Send order confirmation email to customer"
    args_schema: Type[BaseModel] = EmailInput
    return_direct: bool = True

    async def _arun(self, 
                    to: str, 
                    subject: str, 
                    body: str):
        

        print(f"Sending email to {to}: {subject}\n{body}")

        output = {"success": True, "message": f"Email sent to {to}"}
        return json.dumps(output)

    def _run(self, *args, **kwargs):
        raise NotImplementedError("Sync not supported")




