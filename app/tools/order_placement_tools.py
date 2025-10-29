import json
import uuid
import logging
from typing import Type, Optional, List
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.config.settings import settings
from app.config.constants import constants
from app.config.loggings import setup_logging
from app.schemas.order_placement_schema import OrderPlacementInput
from app.database.engine import AsyncSessionLocal
from app.database.models import Inventory, ShoppingCart, Orders, InventoryAudit, OrderAudit

# --- Setup logging ---
setup_logging(level=logging.DEBUG)
logger = logging.getLogger(__name__)

SENDGRID_API_KEY = settings.SENDGRID_API_KEY


# --------------------------
# Utility Functions
# --------------------------
def json_struc(msg: str) -> str:
    """Return a structured JSON message for consistent responses."""
    return json.dumps({"output": msg})


def gen_order_number() -> str:
    """Generate a unique order number."""
    return f"ORD-{uuid.uuid4().hex[:8].upper()}"


def send_order_confirmation_email(to_email: str, order_number: str, items: list, total: float) -> bool:
    """Send order confirmation email using SendGrid. Returns success flag."""
    logger.info(f"Preparing order confirmation email for {to_email} (Order {order_number})")

    try:
        item_lines = "<br>".join([f"{name} ({qty} @ ${price:.2f})" for name, qty, price in items])
        body = (
            f"<strong>Your order {order_number} has been placed successfully!</strong><br><br>"
            f"<b>Items:</b><br>{item_lines}<br><br>"
            f"<b>Total:</b> ${total:.2f}<br><br>"
            f"Thank you for shopping with us!"
        )

        message = Mail(
            from_email="sdfarheen05@gmail.com",
            to_emails=to_email,
            subject=f"Order Confirmation - {order_number}",
            html_content=body,
        )

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)

        logger.info(f"Order confirmation email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {e}", exc_info=True)
        return False


# --------------------------
# Main Tool
# --------------------------
class OrderPlacementTool(BaseTool):
    """
    Manage cart (add/remove/view) and checkout in one place.

    Invariants:
      - Adding to cart only increases reserved_quantity (never reduces quantity_available).
      - Checkout decreases quantity_available by qty, and releases the same qty from reserved_quantity.
      - All audits record exact before/after values.
      - Confirmation email is sent after successful checkout.
    """

    name: str = "OrderPlacementTool"
    description: str = (
        "Manage cart and place orders. Actions: add_to_cart, remove_from_cart, view_cart, checkout. "
        "SKU must come from SQL query; never fabricate SKUs."
    )

    args_schema: Type[BaseModel] = OrderPlacementInput
    return_direct: bool = False

    session_token: str = Field(..., exclude=True, description="Bound session id; do not expose to LLM")

    async def _arun(self, action: str, sku: Optional[str] = None, quantity: Optional[int] = None,customer_email: Optional[str] = None) -> str:
        async with AsyncSessionLocal() as db:
            try:
                if action == "add_to_cart":
                    return await self._add_to_cart(db, sku, quantity or 1)
                elif action == "remove_from_cart":
                    return await self._remove_from_cart(db, sku, quantity or 1)
                elif action == "view_cart":
                    return await self._view_cart(db)
                elif action == "checkout":
                    return await self._checkout(db,customer_email=customer_email or constants.DEFAULT_USER_EMAIL)
                else:
                    return json_struc("Unsupported action.")
            except Exception as e:
                await db.rollback()
                logger.error(f"OrderPlacementTool failed: {str(e)}", exc_info=True)
                return json_struc(f"Error: {str(e)}")

    # --------------------------
    # Cart Management
    # --------------------------
    async def _add_to_cart(self, db: AsyncSession, sku: str, qty: int) -> str:
        if not sku:
            return json_struc("SKU is required to add to cart.")

        inv_row = (
            await db.execute(select(Inventory).where(and_(Inventory.sku == sku, Inventory.status == "ACTIVE")))
        ).scalar_one_or_none()

        if not inv_row:
            return json_struc("Unable to process request because SKU was not found in inventory.")

        free = inv_row.quantity_available - inv_row.reserved_quantity
        if free <= 0:
            return json_struc(f"{inv_row.product_name} is currently out of stock.")

        add_qty = min(qty, free)
        if add_qty <= 0:
            return json_struc(f"Not enough stock to add {inv_row.product_name}.")

        cart_row = (
            await db.execute(
                select(ShoppingCart).where(
                    and_(ShoppingCart.session_id == self.session_token, ShoppingCart.sku == sku)
                )
            )
        ).scalar_one_or_none()

        if cart_row:
            cart_row.quantity += add_qty
            cart_row.price_when_added = inv_row.price
        else:
            db.add(
                ShoppingCart(
                    session_id=self.session_token,
                    sku=sku,
                    quantity=add_qty,
                    price_when_added=inv_row.price,
                )
            )

        prev_reserved = inv_row.reserved_quantity
        inv_row.reserved_quantity = prev_reserved + add_qty

        db.add(
            InventoryAudit(
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
                remarks=f"Added {add_qty} {sku} to cart",
            )
        )

        await db.commit()
        return await self._view_cart(db, prefix=f"Added {add_qty} {inv_row.product_name} to your cart.\n")

    async def _remove_from_cart(self, db: AsyncSession, sku: str, qty: int) -> str:
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
                new_available=inv_row.quantity_available,
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

    async def _view_cart(self, db: AsyncSession, prefix: str = "") -> str:
        rows = (
            await db.execute(
                select(ShoppingCart, Inventory.product_name)
                .join(Inventory, ShoppingCart.sku == Inventory.sku)
                .where(ShoppingCart.session_id == self.session_token)
            )
        ).all()

        if not rows:
            msg = "Your cart is empty."
            return json_struc(prefix + msg if prefix else msg)

        lines, total = [], 0.0
        for cart, product_name in rows:
            subtotal = float(cart.price_when_added) * cart.quantity
            total += subtotal
            lines.append(f"{product_name} x {cart.quantity} = ${subtotal:.2f}")

        body = (
            prefix
            + "Cart items:\n"
            + "\n".join(lines)
            + f"\nTotal: ${total:.2f}\nDo you want to checkout?"
        )
        return json_struc(body)

    # --------------------------
    # Checkout
    # --------------------------
    async def _checkout(self, db: AsyncSession,customer_email) -> str:
        rows = (
            await db.execute(
                select(ShoppingCart, Inventory)
                .join(Inventory, ShoppingCart.sku == Inventory.sku)
                .where(ShoppingCart.session_id == self.session_token)
                .with_for_update()
            )
        ).all()

        if not rows:
            return json_struc("Your cart is empty. Cannot place an order.")

        order_number = gen_order_number()
        grand_total = 0.0

        for cart, inv in rows:
            qty = cart.quantity
            unit_price = float(cart.price_when_added)
            total_price = unit_price * qty
            grand_total += total_price

            prev_available = inv.quantity_available
            prev_reserved = inv.reserved_quantity
            new_available = max(0, prev_available - qty)
            new_reserved = max(0, prev_reserved - qty)

            inv.quantity_available = new_available
            inv.reserved_quantity = new_reserved
            db.add(inv)

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
            await db.flush()

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

        for cart, _ in rows:
            await db.delete(cart)

        await db.commit()

        item_lines = [
            f"{inv.product_name} ({cart.quantity} @ ${float(cart.price_when_added):.2f})"
            for cart, inv in rows
        ]
        summary = (
            f"Your order ({order_number}) has been placed successfully.\n"
            f"Items:\n- " + "\n- ".join(item_lines) + f"\nTotal: ${grand_total:.2f}"
        )

        email_items = [(inv.product_name, cart.quantity, float(cart.price_when_added)) for cart, inv in rows]
        default_email = customer_email

        email_sent = send_order_confirmation_email(
            to_email=default_email,
            order_number=order_number,
            items=email_items,
            total=grand_total,
        )

        email_status = "✅ Confirmation email sent successfully." if email_sent else "⚠️ Order placed, but email delivery failed."

        final_msg = f"{summary}\n\n{email_status} ({default_email})"
        logger.info(f"OrderPlacementTool completed: {final_msg}")
        return json_struc(final_msg)

    def _run(self, *args, **kwargs):
        raise NotImplementedError("Use async mode only.")
