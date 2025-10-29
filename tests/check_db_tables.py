import asyncio
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from app.database.engine import engine


EXPECTED_TABLES = ["Inventory", "InventoryAudit", "Orders", "OrderAudit", \
                   "ShoppingCart","UserSessions"]


async def main():

    try:
        async with engine.begin() as conn:

            def check_tables(sync_conn):

                inspector = inspect(sync_conn)
                tables = inspector.get_table_names()

                print("Tables found in DB:", tables)

                missing = set(EXPECTED_TABLES) - set(tables)

                if missing:
                    print(f"Missing tables:", missing)

                else:
                    print("All expected tables are present and connected!")

            await conn.run_sync(check_tables)

    except SQLAlchemyError as e:
        print("Database error occurred:", e)

    except Exception as e:
        print("Unexpected error:", e)
        
    finally:
    # Dispose before event loop closes
        await engine.dispose()


if __name__ == "__main__":
    
    asyncio.run(main())
  