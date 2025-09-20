from sqlalchemy.ext.asyncio import AsyncSession
from app.database import models


async def create_order(db: AsyncSession,
                       product_id: int,
                       quantity: int,
                       remarks: str = "Ordered"):
    

    order = models.Order(product_id = product_id,
                         quantity= quantity,
                         remarks = remarks)
    

    db.add(order)

    await db.flush()
    await db.refresh(order)   
    return order
