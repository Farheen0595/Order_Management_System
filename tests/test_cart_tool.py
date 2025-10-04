import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy import select, delete

from app.tools.order_placement_tools import OrderPlacementTool
from app.database.engine import engine, AsyncSessionLocal
from app.database.models import UserSessions, Inventory, Orders, InventoryAudit, OrderAudit


# Test values
SESSION_ID = "test-session-002"
SKU = "TEST-SKU-123"
PRODUCT_NAME = "Test Laptop"


async def seed_environment():
    """Prepare UserSessions and Inventory for testing checkout."""
    async with AsyncSessionLocal() as db:
        async with db.begin():
            # Clear out old data for clean test
            await db.execute(delete(Orders).where(Orders.session_id == SESSION_ID))
            await db.execute(delete(OrderAudit).where(OrderAudit.order_number.like("ORD-%")))
            await db.execute(delete(InventoryAudit).where(InventoryAudit.sku == SKU))
            await db.execute(delete(Inventory).where(Inventory.sku == SKU))
            await db.execute(delete(UserSessions).where(UserSessions.session_id == SESSION_ID))

            # Add session
            db.add(UserSessions(
                session_id=SESSION_ID,
                user_name="Checkout Tester",
                expires_at=datetime.utcnow() + timedelta(hours=1),
                status="ACTIVE"
            ))

            # Add inventory item
            db.add(Inventory(
                sku=SKU,
                product_name=PRODUCT_NAME,
                category="Electronics",
                brand="UnitTest",
                description="Checkout flow test item",
                quantity_available=10,
                reserved_quantity=0,
                reorder_level=1,
                price=500.00,
                currency="USD"
            ))


async def run_checkout_test():
    await seed_environment()

    tool = OrderPlacementTool(session_token=SESSION_ID)

    print("\n1️⃣ Add 4 items to cart:")
    result = await tool._arun(action="add_to_cart", sku=SKU, quantity=4)
    print(json.loads(result)["output"])

    print("\n2️⃣ View cart (should show 4 items reserved):")
    result = await tool._arun(action="view_cart")
    print(json.loads(result)["output"])

    print("\n3️⃣ Checkout (should succeed):")
    result = await tool._arun(action="checkout")
    print(json.loads(result)["output"])

    # Validate DB state after checkout
    async with AsyncSessionLocal() as db:
        print("\n📦 Orders table entries:")
        res = await db.execute(select(Orders).where(Orders.session_id == SESSION_ID))
        for order in res.scalars().all():
            print(f"OrderNumber={order.order_number}, SKU={order.sku}, Qty={order.quantity}, Status={order.status}, Total={order.total_price}")

        print("\n📝 OrderAudit table entries:")
        res = await db.execute(select(OrderAudit).where(OrderAudit.order_number.like("ORD-%")))
        for audit in res.scalars().all():
            print(f"AuditID={audit.audit_id}, Order={audit.order_number}, SKU={audit.sku}, From={audit.previous_status}, To={audit.new_status}")

        print("\n📊 InventoryAudit table entries:")
        res = await db.execute(select(InventoryAudit).where(InventoryAudit.sku == SKU))
        for audit in res.scalars().all():
            print(f"AuditID={audit.audit_id}, SKU={audit.sku}, Change={audit.change_type}, QTY={audit.quantity_changed}, PrevAvail={audit.previous_available}, NewAvail={audit.new_available}, PrevRes={audit.previous_reserved}, NewRes={audit.new_reserved}")

        print("\n📦 Inventory final state:")
        inv = await db.get(Inventory, SKU)
        print(f"Available={inv.quantity_available}, Reserved={inv.reserved_quantity}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_checkout_test())
