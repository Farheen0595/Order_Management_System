from typing import Type, Optional, List
from langchain.tools import BaseTool
from decimal import Decimal
from pydantic import BaseModel, Field
from sqlalchemy import select, update, insert, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import pytz
import json
import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.database.engine import AsyncSessionLocal
from app.database.models import Orders, OrderAudit, Inventory, InventoryAudit
from app.config.settings import settings
from app.config.loggings import setup_logging
from app.config.constants import constants
from app.schemas.order_cancellation_schema import OrderCancellationInput

# --- Setup logging ---
setup_logging(level=logging.DEBUG)
logger = logging.getLogger(__name__)

SENDGRID_API_KEY = settings.SENDGRID_API_KEY
IST = pytz.timezone("Asia/Kolkata")


# --------------------------
# Utility Functions
# --------------------------
def json_struc(msg: str) -> str:
    """Return a JSON structured message for consistent LLM response."""
    return json.dumps({"output": msg})


def send_cancellation_email(to_email: str, subject: str, body: str) -> bool:
    """Send order cancellation email using SendGrid and return success flag."""
    logger.info(f"Sending cancellation email to {to_email} for subject: {subject}")
    try:
        message = Mail(
            from_email="sdfarheen05@gmail.com",
            to_emails=to_email,
            subject=subject,
            html_content=f"<strong>{body}</strong>",
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        logger.info(f"Cancellation email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send cancellation email: {str(e)}", exc_info=True)
        return False


# --------------------------
# Order Cancellation Tool
# --------------------------
class OrderCancellationTool(BaseTool):
    """
    Cancels an existing order, restores stock, writes InventoryAudit / OrderAudit,
    and notifies the customer via email.

    JSON-based output only. Messages are clear, emoji-friendly, and user-ready.
    """

    name: str = "OrderCancellationTool"
    description: str = (
        "Cancels an existing order, restores stock, updates audits, "
        "and sends an email notification to the customer."
    )

    args_schema: Type[BaseModel] = OrderCancellationInput
    session_token: str = Field(..., exclude=True, description="Bound session id; not exposed to LLM")

    async def _arun(self, action: str, order_number: str, reason: Optional[str] = None) -> str:
        """Async execution handler for order cancellation."""
        logger.info(f"Processing action '{action}' for order: {order_number}")

        if action != "cancel_order":
            logger.warning(f"Invalid action attempted: {action}")
            return json_struc("Invalid action. Only 'cancel_order' is supported.")

        async with AsyncSessionLocal() as db:
            try:
                result = await self._cancel_order(db, order_number, reason)
                logger.info(f"Order cancellation completed for {order_number}")
                return result
            except Exception as e:
                await db.rollback()
                logger.error(f"Order cancellation failed: {str(e)}", exc_info=True)
                return json_struc("Unable to process the cancellation at this time. Please try again later.")


    async def _cancel_order(self, db: AsyncSession, order_number: str, reason: Optional[str]) -> str:

        logger.debug(f"Starting cancellation process for order {order_number}")

        rows_result = await db.execute(
            select(Orders).where(and_(Orders.order_number == order_number, Orders.session_id == self.session_token))
        )
        order_rows: List[Orders] = rows_result.scalars().all()

        if not order_rows:
            logger.warning(f"Order not found: {order_number}")
            return json_struc(f"Order Number {order_number} was not found.")

        BLOCKED = {"CANCELLED"}
        eligible = [r for r in order_rows if (r.status or "").upper() not in BLOCKED]
        ineligible = [r for r in order_rows if (r.status or "").upper() in BLOCKED]

        if not eligible:
            statuses = ", ".join(sorted({(r.status or "").upper() for r in order_rows}))
            return json_struc(f"Order {order_number} cannot be cancelled. Current status: {statuses}.")

        total_refund = Decimal("0.00")
        cancelled_summaries = []
        now = datetime.now(IST)
        default_email = getattr(constants, "DEFAULT_EMAIL_SENDER", "sdfarheen05@gmail.com")

        logger.info(f"Processing cancellation for {len(eligible)} items")

        for row in eligible:
            qty = int(row.quantity or 0)
            row_total = Decimal(str(row.total_price))
            total_refund += row_total

            inv_result = await db.execute(select(Inventory).where(Inventory.sku == row.sku))
            inv = inv_result.scalar_one_or_none()

            if inv is not None:
                prev_avail, prev_res = int(inv.quantity_available or 0), int(inv.reserved_quantity or 0)
                new_avail, new_res = prev_avail + qty, prev_res

                await db.execute(
                    update(Inventory)
                    .where(Inventory.sku == row.sku)
                    .values(quantity_available=new_avail)
                )

                await db.execute(
                    insert(InventoryAudit).values(
                        sku=row.sku,
                        change_type="ORDER_CANCEL",
                        quantity_changed=qty,
                        previous_available=prev_avail,
                        new_available=new_avail,
                        previous_reserved=prev_res,
                        new_reserved=new_res,
                        timestamp=now,
                        reference_type="ORDER",
                        reference_id=order_number,
                        session_id=row.session_id,
                        remarks=f"Order {order_number} cancelled",
                    )
                )

            old_status = (row.status or "").upper()
            row.status = "CANCELLED"
            row.remarks = f"Order cancelled. Reason: {reason or 'N/A'}"

            await db.execute(
                insert(OrderAudit).values(
                    order_id=row.id,
                    order_number=order_number,
                    sku=row.sku,
                    previous_status=old_status or "PLACED",
                    new_status="CANCELLED",
                    remarks=reason or "No reason provided",
                    timestamp=now,
                )
            )

            cancelled_summaries.append(f"{row.sku} x {qty}")

        await db.commit()
        logger.info(f"Committed all DB changes for order {order_number}")

        pretty_refund = f"${total_refund:.2f}"

        email_sent = send_cancellation_email(
            to_email=default_email,
            subject=f"Order {order_number} Cancelled",
            body=(
                f"Your order {order_number} has been cancelled successfully.<br>"
                f"Items: {', '.join(cancelled_summaries)}<br>"
                f"Refund Amount: {pretty_refund}"
            ),
        )

        email_status = "Email sent successfully" if email_sent else "Email failed to send"

        if ineligible:
            ineligible_statuses = ", ".join(sorted({(r.status or '').upper() for r in ineligible}))
            msg = (
                    f"Partial cancellation for Order {order_number}.\n"
                    f"Cancelled items: {', '.join(cancelled_summaries)}.\n"
                    f"Not eligible (status: {ineligible_statuses}).\n"
                    f"Refund: {pretty_refund}.\n"
                    f"Email: {email_status} ({default_email})")
        else:
            msg = (
                f"Your order (Number: {order_number}) has been fully cancelled.\n"
                f"Items: {', '.join(cancelled_summaries)}.\n"
                f"Refund: {pretty_refund}.\n"
                f"Email: {email_status} ({default_email})"
            )

        logger.info(f"Final response for order {order_number}: {msg}")
        return json_struc(msg)

    def _run(self, *args, **kwargs):
        logger.warning("Synchronous run attempted but not supported.")
        raise NotImplementedError("This tool only supports async mode (_arun).")
