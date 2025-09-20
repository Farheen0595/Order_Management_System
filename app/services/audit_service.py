from sqlalchemy.ext.asyncio import AsyncSession
from app.database import models

async def order_audit(db: AsyncSession, order_id: int, prev: str, new: str, remarks: str):
    audit = models.OrderAudit(order_id=order_id, previousStatus=prev, newStatus=new, remarks=remarks)
    db.add(audit)
    return audit