from pydantic import BaseModel
from typing import Type
import json
from langchain.tools import BaseTool
from app.database.models import (Orders, OrderAudit, Inventory, InventoryAudit)
from app.database.engine import AsyncSessionLocal
from app.schemas.order_placement_schema import OrderPlacementInput




# ------------------------------
# Combined Order Placement Tool
# ------------------------------


class OrderPlacementTool(BaseTool):

    name: str = "Order_Placement_Tool"
    description: str = "Place a new order: create order, log audit, update inventory, send confirmation email"
    args_schema: Type[BaseModel] = OrderPlacementInput
    return_direct: bool = False

    async def _arun(self, 
                    product_id: int, 
                    quantity: int, 
                    customer_email: str, 
                    remarks: str = "Order placed"):
        

        async with AsyncSessionLocal() as db:

            async with db.begin():

                # ----------------------------
                # Step 1: Create Order
                # ----------------------------

                order = Orders(product_id=product_id, 
                              quantity=quantity, 
                              status="processed",
                            remarks=remarks)
                
                db.add(order)
                await db.flush()
                await db.refresh(order)
                order_id = order.order_id

                # ----------------------------
                # Step 2: Order Audit
                # ----------------------------

                order_audit = OrderAudit( order_id=order_id,
                                        previousStatus=order.status,
                                        newStatus="delivered",
                                        remarks="Order created successfully")
                
                db.add(order_audit)
                await db.flush()
                await db.refresh(order_audit)


                # ----------------------------
                # Step 3: Update Inventory
                # ----------------------------
                inventory = await db.get(Inventory, product_id)

                quantity_available = inventory.quantity_available

                total_price = float(inventory.price * quantity)

                product_name = inventory.product_name

                if not inventory:
                    raise ValueError("Product not found in inventory")

                if inventory.quantity_available < quantity:
                    raise ValueError(f"Insufficient stock: available {inventory.quantity_available}, requested {quantity}")

                inventory.quantity_available -= quantity

                inventory_audit = InventoryAudit(
                                                product_id=product_id,
                                                quantity_available=quantity_available,
                                                changeType="REMOVE",
                                                quantityChanged=quantity,
                                                remarks=f"Order {order_id} deduction")
                
                db.add(inventory_audit)
                await db.flush()
                await db.refresh(inventory)
                await db.refresh(inventory_audit)


                # ----------------------------
                # Step 4: Send Confirmation Email
                # ----------------------------

                email_subject = f"Order Confirmation #{order_id}"
                email_body = f"Your order for {quantity} unit(s) of product {product_id} has been placed successfully."
                print(f"Sending email to {customer_email}: {email_subject}\n{email_body}")

                # Commit transaction
                await db.commit()

                data = {
                    "order": {
                        "order_id": order_id,
                        "quantity": quantity,
                        "status": order.status,
                    },
                    
                    "product_name":product_name,
                    "email": {"to": customer_email},
                    "total_price": float(total_price)
                }

                
                return  json.dumps(data)


    def _run(self, *args, **kwargs):
        raise NotImplementedError("Sync execution not supported, use _arun.")
