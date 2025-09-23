from app.config.settings import settings  
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine      
from sqlalchemy.orm import DeclarativeBase  


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    Inherits from `DeclarativeBase` and serves as the common base
    for defining database tables. All ORM models should subclass this
    `Base` to gain SQLAlchemy's declarative capabilities, such as
    table mapping, metadata management, and schema generation.

    Attributes:
        None directly in this class. Attributes are defined in subclasses.
    """
    pass


# Construct the async database URL using settings from your config
db_url = f"mysql+aiomysql://{settings.DB_USERNAME}:{settings.DB_PASSWORD}" \
         f"@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}"




# Create an async engine for connecting to the database
# - pool_size: number of connections to keep in the pool
# - max_overflow: max number of connections above pool_size
# - pool_pre_ping: test connections before using them
# - echo: if True, SQLAlchemy will log all SQL statements (useful for debugging)
engine: AsyncEngine = create_async_engine(
    url=db_url,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_POOL_OVERFLOW,
    pool_pre_ping=True,
    echo=True
)



# Create an async session factory
# - expire_on_commit=False: prevents SQLAlchemy from expiring objects after commit
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False
)
