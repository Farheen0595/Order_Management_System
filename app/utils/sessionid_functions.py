from datetime import datetime, timedelta
from app.database.engine import AsyncSessionLocal
from app.database.models import UserSessions,ShoppingCart
from sqlalchemy import select
import pytz
import logging


# Setup logging
logger = logging.getLogger(__name__)


IST = pytz.timezone("Asia/Kolkata")

async def ensure_session(session_id: str, 
                         user_name: str = "Guest User", 
                         ttl_minutes: int = 1440): # 24 hour
    
    """
    Ensure a session exists in DB.
    - New session → create with expiry (default 24h).
    - Existing & expired → mark as expired.
    - Existing & active → extend expiry (sliding window).
    """

    logger.info(f"Ensuring session for ID: {session_id}, User: {user_name}")
    logger.debug(f"TTL minutes: {ttl_minutes}")

    async with AsyncSessionLocal() as db:

        async with db.begin():

            logger.debug(f"Checking for existing session: {session_id}")
            existing = await db.get(UserSessions, session_id)

            now = datetime.now(IST)
            expiry_time = now + timedelta(minutes=ttl_minutes)
            logger.debug(f"Current time (IST): {now}, Expiry time: {expiry_time}")

            if not existing:

                # New session id will get created
                logger.info(f"Creating new session for {session_id}")
                session = UserSessions(session_id=session_id,
                                        user_name=user_name,
                                        expires_at=expiry_time,
                                        status="ACTIVE")
                db.add(session)
                logger.debug(f"New session created with expiry: {expiry_time}")


            else:
                
                logger.debug(f"Found existing session: {session_id}")
                # Normalize DB datetime (force IST)
                expires_at = existing.expires_at
                
                if expires_at and expires_at.tzinfo is None:
                    logger.debug(f"Localizing naive datetime: {expires_at}")
                    expires_at = IST.localize(expires_at)

                if expires_at and expires_at < now:

                    logger.info(f"Session {session_id} has expired. Marking as EXPIRED")
                    existing.status = "EXPIRED"

                    # records = await db.execute(select(ShoppingCart).where(ShoppingCart.session_id == session_id))
                    # cart_items = records.scalars().all()

                    # for item in cart_items:
                    #     await db.delete(item)

                    # await db.commit()
                    # logger.debug(f"Deleted {len(cart_items)} items from ShoppingCart for session {session_id}")
                    
                elif existing.status == "ACTIVE":
                    logger.debug(f"Updating last activity for active session: {session_id}")
                    existing.last_activity = now
                    
                    # Uncomment if you want sliding window
                    # existing.expires_at = expiry_time

        logger.debug("Committing Session Changes to database")
        await db.commit()
        logger.info(f"User Session operation completed for {session_id}")
