from pydantic import BaseModel
from typing import Type
from langchain.tools import BaseTool
from app.database.models import (Orders, OrderAudit, Inventory, InventoryAudit)
from app.database.engine import AsyncSessionLocal
from app.schemas.order_cancellation_schema import OrderCancellationtInput
import json




# ------------------------------
# Combined Order Placement Tool
# ------------------------------


class OrderCancellationTool(BaseTool):

    name: str = "Order_Cancellation_Tool"
    description: str = "Cancel an order: log order, log order audit, update inventory,log inventory audit and send confirmation email"
    args_schema: Type[BaseModel] = OrderCancellationtInput
    return_direct: bool = False

    async def _arun(self, 
                    order_id: int,
                    **kwargs):
        

        async with AsyncSessionLocal() as db:

            async with db.begin():

                # ----------------------------
                #  Search Order Table
                # ----------------------------

                args = self.args_schema(order_id=order_id,**kwargs)

                orders = await db.get(Orders,order_id)

                ordered_quantity = orders.quantity
                ordered_product_id = orders.product_id
                ordered_remarks = args.reason
                previousStatus = orders.status
                ordered_status = "Cancelled"


                orders.quantity = 0
                orders.status = ordered_status
                orders.remarks = ordered_remarks


                await db.flush()
                await db.refresh(orders)

                # # ----------------------------
                # #  Order Audit
                # # ----------------------------

                newStatus = orders.status
                orderauditremarks = orders.remarks

                order_audit = OrderAudit(order_id=order_id,
                                        previousStatus=previousStatus,
                                        newStatus=newStatus,
                                        remarks=orderauditremarks)
                
                db.add(order_audit)
                await db.flush()
                await db.refresh(order_audit)


                # # ----------------------------
                # #  Update Inventory
                # ----------------------------
                inventory = await db.get(Inventory, ordered_product_id)

                old_quantity_available = inventory.quantity_available

                inventory.quantity_available += ordered_quantity

                inventory_audit = InventoryAudit(
                                                product_id=ordered_product_id,
                                                quantity_available=old_quantity_available,
                                                changeType="ADD",
                                                quantityChanged=+ordered_quantity,
                                                remarks=f"Order {order_id} addition")
                
                db.add(inventory_audit)
                await db.flush()
                await db.refresh(inventory)
                await db.refresh(inventory_audit)

                total_refund = float(inventory.price*ordered_quantity)

                # -------------------------------------------------
                # Send Confirmation Email for the Cancelled Order
                # ------------------------------------------------

                email_subject = f"Order Cancelled #{order_id}"
                email_body = f"Your order for {ordered_quantity} unit(s) of product {inventory.product_name} has been cancelled successfully."
                print(f"Sending email to {args.email_address}: {email_subject}\n{email_body}")

                # Commit transaction
                await db.commit()

                data = {
                        "order": {
                                        "order_id": order_id,
                                        "status": orders.status},
                    
                    "product_name":inventory.product_name,
                    "email": {"to": args.email_address},
                    "total_refund": total_refund
                }

                
                return  json.dumps(data)


    def _run(self, *args, **kwargs):
        raise NotImplementedError("Sync execution not supported, use _arun.")
    


