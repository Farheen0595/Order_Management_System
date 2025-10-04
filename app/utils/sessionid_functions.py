from datetime import datetime
from datetime import timedelta
from datetime import timezone
from app.database.engine import AsyncSessionLocal
from app.database.models import UserSessions
import pytz



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

    async with AsyncSessionLocal() as db:
        async with db.begin():
            existing = await db.get(UserSessions, session_id)

            now = datetime.now(IST)
            expiry_time = now + timedelta(minutes=ttl_minutes)

            if not existing:
                # New session
                session = UserSessions(
                    session_id=session_id,
                    user_name=user_name,
                    expires_at=expiry_time,
                    status="ACTIVE"
                )
                db.add(session)

            else:

                # Normalize DB datetime (force IST)
                expires_at = existing.expires_at
                
                if expires_at and expires_at.tzinfo is None:
                    expires_at = IST.localize(expires_at)

                if expires_at and expires_at < now:
                    existing.status = "EXPIRED"
                elif existing.status == "ACTIVE":
                    existing.last_activity = now
                    # Uncomment if you want sliding window
                    # existing.expires_at = expiry_time

        await db.commit()
