from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import models


async def product_exists(db: AsyncSession, name: str) -> bool:

    query = select(models.Inventory).where(models.Inventory.product_name.ilike(f"%{name}%"))

    res = await db.execute(query)

    return res.scalars().first(),True


async def update_inventory(
                            db: AsyncSession,
                            product_id: int,
                            quantity: int,
                            changeType: str,
                            remarks: str

                        ):
    inv = await db.get(models.Inventory, product_id)
    if not inv:
        raise ValueError("Product not found")

    quantity_available   = inv.quantity_available
    # Update inventory based on changeType
    if changeType.upper() == "REMOVE":
        if inv.quantity_available < quantity:
            raise ValueError("Insufficient stock")
        inv.quantity_available -= quantity

    elif changeType.upper() == "ADD":
        inv.quantity_available += quantity

    elif changeType.upper() == "SET":
        inv.quantity_available = quantity

    else:
        raise ValueError(f"Invalid changeType: {changeType}")

    log_audit = models.InventoryAudit(
        product_id=product_id,
        quantity_available = quantity_available,
        changeType=changeType.upper(),
        quantityChanged=quantity if changeType.upper() != "REMOVE" else -quantity,
        remarks=remarks,
    )

    await db.flush()
    await db.refresh(inv)
    await db.commit()

    return inv








