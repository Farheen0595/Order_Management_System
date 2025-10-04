import json
import uuid
from typing import Type, Optional, List

from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.order_placement_schema import OrderPlacementInput
from app.database.engine import AsyncSessionLocal
from app.database.models import Inventory,ShoppingCart,Orders,InventoryAudit,OrderAudit



def gen_order_number() -> str:
    return f"ORD-{uuid.uuid4().hex[:8].upper()}"

def json_struc(msg: str) -> str:
    return json.dumps({"output": msg})


class OrderPlacementTool(BaseTool):

    """
    Manage cart (add/remove/view) and checkout in one place.

    Invariants:
      - Adding to cart only increases reserved_quantity (never reduces quantity_available).
      - Checkout decreases quantity_available by qty, and releases the same qty from reserved_quantity.
      - All audits record exact before/after values.
    """



    name: str = "Order_Placement_Tool"
    description: str = ( "Manage cart and place orders. Actions: add_to_cart, remove_from_cart, view_cart, checkout. "
                          "SKU must come from SQL query; never fabricate SKUs.")
    
    args_schema: Type[BaseModel] = OrderPlacementInput
    return_direct: bool = False

    session_token: str = Field(...,
                            exclude=True, 
                            description="Bound session id; do not expose to LLM")


    async def _arun(self, 
                    action: str,
                    sku: Optional[str] = None, 
                    quantity: Optional[int] = None):
        
        async with AsyncSessionLocal() as db:

            try:
                if action == "add_to_cart":

                    return await self._add_to_cart(db, sku, quantity or 1)
                
                elif action == "remove_from_cart":

                    return await self._remove_from_cart(db, sku, quantity or 1)
                
                elif action == "view_cart":

                    return await self._view_cart(db)
                
                elif action == "checkout":

                    return await self._checkout(db)
                
                else:
                    return json_struc("Unsupported action.")
                
                
            except Exception as e:

                await db.rollback()

                return json_struc(f"Error: {str(e)}")




    async def _add_to_cart(self, 
                           db: AsyncSession, 
                           sku: str,
                            qty: int) -> str:
        
        if not sku:

            return json_struc("SKU is required to add to cart.")

        inv_row = (await db.execute(select(Inventory).where(and_(Inventory.sku == sku, Inventory.status == "ACTIVE")))).scalar_one_or_none()

        if not inv_row:

            return json_struc("Unable to process request because SKU was not found in inventory.")
        

        free = inv_row.quantity_available - inv_row.reserved_quantity

        if free <= 0:

            return json_struc(f"{inv_row.product_name} is currently out of stock.")

        add_qty = min(qty, free)

        if add_qty <= 0:

            return json_struc(f"Not enough stock to add {inv_row.product_name}.")

        cart_row = (await db.execute(select(ShoppingCart).where(and_(ShoppingCart.session_id == self.session_token, ShoppingCart.sku == sku)))).scalar_one_or_none()

        if cart_row:
            cart_row.quantity +=  add_qty
            cart_row.price_when_added = inv_row.price

        else:

            cart_row = ShoppingCart(session_id=self.session_token,
                                    sku=sku,
                                    quantity=add_qty,
                                    price_when_added=inv_row.price,)
            
            db.add(cart_row)

        prev_reserved = inv_row.reserved_quantity

        inv_row.reserved_quantity = prev_reserved + add_qty  # reserve only

        db.add(InventoryAudit(
                sku=sku,
                change_type="CART_ADD",
                quantity_changed=add_qty,
                previous_available=inv_row.quantity_available,
                new_available=inv_row.quantity_available,  
                previous_reserved=prev_reserved,
                new_reserved=inv_row.reserved_quantity,
                reference_type="CART",
                reference_id=None,
                session_id=self.session_token,
                remarks=f"Added {add_qty} {sku} to cart",))
        

        await db.commit()

        return await self._view_cart(db, prefix=f"Added {add_qty} {inv_row.product_name} to your cart.\n")


    async def _remove_from_cart(self,
                                db: AsyncSession, 
                                sku: str ,
                                qty: int) -> str:
        
        if not sku:

            return json_struc("SKU is required to remove from cart.")


        cart_row = (
            await db.execute(
                select(ShoppingCart).where(
                    and_(ShoppingCart.session_id == self.session_token, ShoppingCart.sku == sku)
                )
            )
        ).scalar_one_or_none()

        if not cart_row:
            return json_struc("This item is not in your cart.")
        

        inv_row = (await db.execute(select(Inventory).where(Inventory.sku == sku))).scalar_one_or_none()

        if not inv_row:
            return json_struc("Inventory not found for this SKU.")


        remove_qty = min(qty, cart_row.quantity)

        cart_row.quantity -= remove_qty

        if cart_row.quantity <= 0:

            await db.delete(cart_row)

        prev_reserved = inv_row.reserved_quantity
        inv_row.reserved_quantity = max(0, prev_reserved - remove_qty)

        db.add(
            InventoryAudit(
                sku=sku,
                change_type="CART_REMOVE",
                quantity_changed=remove_qty,
                previous_available=inv_row.quantity_available,
                new_available=inv_row.quantity_available,  # unchanged on cart remove
                previous_reserved=prev_reserved,
                new_reserved=inv_row.reserved_quantity,
                reference_type="CART",
                reference_id=None,
                session_id=self.session_token,
                remarks=f"Removed {remove_qty} {sku} from cart",
            )
        )

        await db.commit()
        return await self._view_cart(db, prefix=f"Removed {remove_qty} item(s).\n")


    async def _view_cart(self, 
                         db: AsyncSession, 
                         prefix: str = "") -> str:
        
        rows = (await db.execute(
                select(ShoppingCart, Inventory.product_name)
                .join(Inventory, ShoppingCart.sku == Inventory.sku)
                .where(ShoppingCart.session_id == self.session_token))).all()


        if not rows:

            msg = "Your cart is empty."

            return json_struc(prefix + msg if prefix else msg)


        lines: List[str] = []

        total = 0.0

        for cart, product_name in rows:

            subtotal = float(cart.price_when_added) * cart.quantity
            total += subtotal
            lines.append(f"{product_name} x {cart.quantity} = ${subtotal:.2f}")


        body = (
            prefix
            + "Cart items:\n"
            + "\n".join(lines)
            + f"\nTotal: ${total:.2f}\n Do you want to checkout?"
        )

        return json_struc(body)

    async def _checkout(self, db: AsyncSession) -> str:

        """
        - Locks inventory rows (FOR UPDATE) to prevent races.
        - Deducts quantity_available by the purchased qty (once), and releases the same qty from reserved_quantity.
        - Writes consistent audits with exact before/after values.
        """
        

        # Pull current cart + lock inventory rows

        rows = (
            await db.execute(
                select(ShoppingCart, Inventory)
                .join(Inventory, ShoppingCart.sku == Inventory.sku)
                .where(ShoppingCart.session_id == self.session_token)
                .with_for_update()   # <-- lock the joined rows (Inventory) for this transaction
            )).all()


        if not rows:
            return json_struc("Your cart is empty. Cannot place an order.")

        # Validate enough stock (considering reservations already held by this session)

        for cart, inv in rows:
            # Effective free stock for this cart line is already reserved for this session,
            # but we still guard against negatives.

            if cart.quantity <= 0:
                return json_struc("Cart contains invalid quantity.")
            
            if inv.reserved_quantity <= 0:
                # Should not happen if add_to_cart worked properly; still guard

                return json_struc(f"Item {inv.sku} appears not reserved. Please re-add to cart.")

        order_number = gen_order_number()
        grand_total = 0.0


        for cart, inv in rows:
            qty = cart.quantity
            unit_price = float(cart.price_when_added)
            total_price = unit_price * qty
            grand_total += total_price

            # Capture previous values BEFORE mutation
            prev_available = inv.quantity_available
            prev_reserved = inv.reserved_quantity

            # Deduct from available ONCE and release the same qty from reserved
            new_available = max(0, prev_available - qty)
            new_reserved = max(0, prev_reserved - qty)

            # Sanity guard: we must not deduct more than what's reserved

            # If reservation somehow drifted, clamp to valid domain
            if prev_reserved < qty:
                # clamp to what's reserved (should not normally happen)

                qty_to_release = prev_reserved
                # recompute new_available using the original purchase quantity (still deduct)
                new_reserved = 0

                new_available = max(0, prev_available - qty)
            else:
                qty_to_release = qty

            inv.quantity_available = new_available
            inv.reserved_quantity = new_reserved
            db.add(inv)

            # Create order line
            order_row = Orders(
                order_number=order_number,
                session_id=self.session_token,
                sku=inv.sku,
                quantity=qty,
                unit_price=unit_price,
                total_price=total_price,
                status="PLACED",
                remarks="Order placed",
            )
            db.add(order_row)
            await db.flush()  # to get order_row.id for OrderAudit

            # Inventory audit: exact before/after
            db.add(
                InventoryAudit(
                    sku=inv.sku,
                    change_type="ORDER_PLACED",
                    quantity_changed=qty,
                    previous_available=prev_available,
                    new_available=new_available,
                    previous_reserved=prev_reserved,
                    new_reserved=new_reserved,
                    reference_type="ORDER",
                    reference_id=order_number,
                    session_id=self.session_token,
                    remarks=f"Order {order_number} placed for {qty} {inv.sku}",
                )
            )

            # Order audit: PENDING -> PLACED
            db.add(
                OrderAudit(
                    order_id=order_row.id,
                    order_number=order_number,
                    sku=inv.sku,
                    previous_status="PENDING",
                    new_status="PLACED",
                    remarks="Order created successfully",
                )
            )

        # Clear cart
        for cart, _ in rows:
            await db.delete(cart)

        await db.commit()

        item_lines = [
            f"{inv.product_name} ({cart.quantity} @ ${float(cart.price_when_added):.2f})"
            for cart, inv in rows
        ]
        summary = (
            f"Your order ({order_number}) has been placed.\n"
            f"Items:\n- " + "\n- ".join(item_lines) + f"\nTotal: ${grand_total:.2f}"
        )
        return json_struc(summary)
    

    def _run(self, *args, **kwargs):
        raise NotImplementedError("Use async mode")