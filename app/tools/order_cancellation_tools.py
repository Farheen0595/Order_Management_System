from typing import Type, Optional,List
from langchain.tools import BaseTool
from decimal import Decimal
from pydantic import BaseModel
from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json
import pytz
from app.database.engine import AsyncSessionLocal
from app.database.models import Orders, OrderAudit, Inventory, InventoryAudit
from app.config.settings import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.schemas.order_cancellation_schema import OrderCancellationInput

SENDGRID_API_KEY = settings.SENDGRID_API_KEY


IST = pytz.timezone("Asia/Kolkata")


def send_cancellation_email(to_email: str, subject: str, body: str) -> None:
    """Send order cancellation email using SendGrid."""
    try:
        message = Mail(
            from_email="sdfarheen05@gmail.com",
            to_emails=to_email,
            subject=subject,
            html_content=f"<strong>{body}</strong>",
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)

    except Exception as e:
        print(f"[OrderCancellationTool] Email error: {e}")



class OrderCancellationTool(BaseTool):

    """
    Cancels an existing order, restores stock, writes InventoryAudit / OrderAudit,
    and notifies the customer via email.

    IMPORTANT:
    - Your Orders table holds **one row per SKU** for the same order_number.
    - We cancel all *eligible* rows (status NOT in CANCELLED/SHIPPED/DELIVERED).
    - Inventory logic mirrors your Placement flow:
        * At checkout, you *already* reduced `quantity_available` and released `reserved`.
        * On cancel, we revert: `quantity_available += ordered_quantity`. Reserved stays unchanged.
    - InventoryAudit row must include all mandatory columns shown in your schema snapshot.
    """

    name: str = "Order_Cancellation_Tool"
    description: str = (
        "Cancels an existing order (one or more rows in Orders for the same order_number), "
        "restores stock, updates audits, and emails the customer."
    )
    args_schema: Type[BaseModel] = OrderCancellationInput



    async def _arun(
                    self,
                    action: str,
                    order_number: str,
                    reason: Optional[str] = None)-> str:
        

        if action != "cancel_order":
            return '{"output": "Invalid action. Only \'cancel_order\' is supported."}'


        async with AsyncSessionLocal() as db:

            try:

                return await self._cancel_order(db, order_number, reason)
            
            except Exception as e:
                await db.rollback()
                print(f"[OrderCancellationTool] Error: {e}")
                return '{"output": "Unable to process the cancellation at this time. Please try again later."}'



    async def _cancel_order(
                        self,
                        db: AsyncSession,
                        order_number: str,
                        reason: Optional[str]) -> str:


        rows_result = await db.execute(select(Orders).where(Orders.order_number == order_number))

        order_rows: List[Orders] = rows_result.scalars().all()

        if not order_rows:
            return f'{{"output": "Order Number {order_number} was not found."}}'

        # Identify eligibility
        BLOCKED = {"CANCELLED", "DELIVERED", "SHIPPED"}\
        
        eligible: List[Orders] = [r for r in order_rows if (r.status or "").upper() not in BLOCKED]

        ineligible: List[Orders] = [r for r in order_rows if (r.status or "").upper() in BLOCKED]

        if not eligible:

            statuses = ", ".join(sorted({(r.status or "").upper() for r in order_rows}))

            return (f'{{"output": "Order {order_number} cannot be cancelled. '
                            f'Current status: {statuses}."}}')


        total_refund: Decimal = Decimal("0.00")
        cancelled_summaries: List[str] = []


        now = datetime.now(IST)
        default_email = getattr(settings, "DEFAULT_CUSTOMER_EMAIL", "dfarheen05@gmail.com")


        for row in eligible:

            
            row_total = Decimal(str(row.total_price or 0))
            total_refund += row_total

            #invent ory for this SKU
            inv_result = await db.execute(select(Inventory).where(Inventory.sku == row.sku))

            inv: Optional[Inventory] = inv_result.scalar_one_or_none()

            if inv is None:

                print(f"[OrderCancellationTool] SKU {row.sku} not found in Inventory during cancel.")

                prev_avail = new_avail = prev_res = new_res = 0

            else:


                prev_avail = int(inv.quantity_available or 0)
                prev_res = int(inv.reserved_quantity or 0)

                qty = int(row.quantity or 0)
                new_avail = prev_avail + qty
                new_res = prev_res  


                # inventory change
                await db.execute(
                    update(Inventory)
                    .where(Inventory.sku == row.sku)
                    .values(quantity_available=new_avail)
                )


                # InventoryAudit 
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


            # Update this order row -> CANCELLED 
            old_status = (row.status or "").upper()
            row.status = "CANCELLED"
            row.remarks = f"Order cancelled. Reason: {reason or 'N/A'}"

            # OrderAudit
            await db.execute(
                insert(OrderAudit).values(
                    order_id = row.id,
                    order_number=order_number,
                    sku=row.sku,
                    previous_status=old_status or "PLACED",
                    new_status="CANCELLED",
                    remarks=reason or "No reason provided",
                    timestamp=now,
                )
            )

            cancelled_summaries.append(f"{row.sku} x {row.quantity}")

        #  Persist everything
        await db.commit()

        # Email notification
        try:
            pretty_refund = f"${total_refund:.2f}"
            send_cancellation_email(
                to_email=default_email,
                subject=f"Order {order_number} Cancelled",
                body=(
                    f"Your order {order_number} has been cancelled successfully.<br>"
                    f"Items: {', '.join(cancelled_summaries)}<br>"
                    f"Refund Amount: {pretty_refund}"
                ),
            )

        except Exception as e:
            print(f"[OrderCancellationTool] Email send failed: {e}")


        # 5) Build user-facing message
        pretty_refund = f"${total_refund:.2f}"

        if ineligible:
            # Partial cancellation
            ineligible_statuses = ", ".join(sorted({(r.status or '').upper() for r in ineligible}))
            return (
                '{'
                f'"output": " Partial cancel for Order {order_number}. '
                f'Cancelled: {", ".join(cancelled_summaries)}. '
                f'Not eligible (status: {ineligible_statuses}). '
                f'Refund: {pretty_refund}."'
                '}'
            )

        # cancellation
        return (
            '{'
            f'"output": " Your order (Number: {order_number}) has been cancelled successfully. '
            f'Items: {", ".join(cancelled_summaries)}. '
            f'Total refund: {pretty_refund}."'
            '}'
        )

    

    def _run(self, *args, **kwargs):
        raise NotImplementedError("This tool only supports async mode (_arun).")
