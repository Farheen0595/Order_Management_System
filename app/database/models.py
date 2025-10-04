# app/db/models.py
from sqlalchemy import (
    Column, String, Integer, DECIMAL,
    Enum, ForeignKey, UniqueConstraint, Text,text
)

from sqlalchemy.dialects.mysql import TIMESTAMP

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.engine import Base


# ===== 1. USER SESSIONS =====
class UserSessions(Base):
    __tablename__ = "UserSessions"

    session_id = Column(String(255), primary_key=True)
    user_name = Column(String(255), default="Guest User")

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP")
    )
    last_activity = Column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP")
    )
    expires_at = Column(TIMESTAMP(timezone=True))
    status = Column(Enum("ACTIVE", "EXPIRED"), default="ACTIVE")
    # relationships
    carts = relationship("ShoppingCart", back_populates="session", cascade="all, delete-orphan")
    orders = relationship("Orders", back_populates="session", cascade="all, delete-orphan")


# ===== 2. INVENTORY =====
class Inventory(Base):
    __tablename__ = "Inventory"

    sku = Column(String(50), primary_key=True)   # ✅ SKU is PK now
    product_name = Column(String(255), nullable=False)
    category = Column(String(255), nullable=False)
    brand = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    quantity_available = Column(Integer, nullable=False)
    reserved_quantity = Column(Integer, default=0)
    reorder_level = Column(Integer, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(10), default="USD")
    warehouse_location = Column(String(255), default="WH-A2")
    status = Column(String(20), default="ACTIVE")

    # relationships
    carts = relationship("ShoppingCart", back_populates="inventory", cascade="all, delete-orphan")
    orders = relationship("Orders", back_populates="inventory", cascade="all, delete-orphan")
    audits = relationship("InventoryAudit", back_populates="inventory", cascade="all, delete-orphan")
    order_audits = relationship("OrderAudit", back_populates="inventory_item", cascade="all, delete-orphan")


# ===== 3. SHOPPING CART =====
class ShoppingCart(Base):
    __tablename__ = "ShoppingCart"

    cart_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), ForeignKey("UserSessions.session_id", ondelete="CASCADE"), nullable=False)
    sku = Column(String(50), ForeignKey("Inventory.sku", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, default=1)
    price_when_added = Column(DECIMAL(10, 2), nullable=False)
    added_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("session_id", "sku", name="unique_session_sku"),)

    # relationships
    session = relationship("UserSessions", back_populates="carts")
    inventory = relationship("Inventory", back_populates="carts")


# ===== 4. ORDERS =====
class Orders(Base):
    __tablename__ = "Orders"

    id = Column(Integer, primary_key=True, autoincrement=True)   # ORM surrogate PK
    order_number = Column(String(50), nullable=False, index=True)  # business key
    session_id = Column(String(255), ForeignKey("UserSessions.session_id"), nullable=False)
    sku = Column(String(50), ForeignKey("Inventory.sku"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    total_price = Column(DECIMAL(10, 2), nullable=False)
    status = Column(
        Enum("PENDING", "PLACED", "CANCELLED", "COMPLETED", name="order_status"),
        default="PENDING",
        nullable=False
    )
    remarks = Column(String(255))
    order_date = Column(TIMESTAMP, server_default=func.now())

    # relationships
    session = relationship("UserSessions", back_populates="orders")
    inventory = relationship("Inventory", back_populates="orders")
    audits = relationship("OrderAudit", back_populates="order", cascade="all, delete-orphan")


# ===== 5. INVENTORY AUDIT =====
class InventoryAudit(Base):
    __tablename__ = "InventoryAudit"

    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), ForeignKey("Inventory.sku", ondelete="CASCADE"), nullable=False)
    change_type = Column(String(20), nullable=False)  # CART_ADD, ORDER_PLACED, ORDER_CANCELLED
    quantity_changed = Column(Integer, nullable=False)
    previous_available = Column(Integer, nullable=False)
    new_available = Column(Integer, nullable=False)
    previous_reserved = Column(Integer, default=0)
    new_reserved = Column(Integer, default=0)
    timestamp = Column(TIMESTAMP, server_default=func.now())
    reference_type = Column(String(20))   # CART, ORDER
    reference_id = Column(String(50))     # order_number
    session_id = Column(String(255), ForeignKey("UserSessions.session_id", ondelete="SET NULL"))
    remarks = Column(String(255), nullable=True)

    # relationship
    inventory = relationship("Inventory", back_populates="audits")


# ===== 6. ORDER AUDIT =====
class OrderAudit(Base):
    __tablename__ = "OrderAudit"

    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("Orders.id", ondelete="CASCADE"), nullable=False)
    order_number = Column(String(50), nullable=False)
    sku = Column(String(50), ForeignKey("Inventory.sku", ondelete="CASCADE"), nullable=False)

    previous_status = Column(String(20), nullable=False)
    new_status = Column(String(20), nullable=False)

    timestamp = Column(TIMESTAMP, server_default=func.now())
    remarks = Column(String(255))

    # relationships
    order = relationship("Orders", back_populates="audits")
    inventory_item = relationship("Inventory", back_populates="order_audits")