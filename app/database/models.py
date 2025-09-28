from sqlalchemy import (
    Column, Integer, String, Numeric, ForeignKey, CheckConstraint,
    Text, TIMESTAMP, func
)
from sqlalchemy.orm import relationship
from app.database.engine import Base


class Inventory(Base):
    """
    Represents the inventory of products in the warehouse.

    Attributes:
        product_id (int): Primary key, auto-incremented product identifier.
        sku (str): Stock Keeping Unit identifier for the product.
        product_name (str): Name of the product.
        category (str): Product category.
        brand (str): Brand of the product.
        description (str): Product description.
        quantity_available (int): Current stock available.
        reorder_level (int): Minimum threshold stock level for reorder.
        price (Decimal): Price of the product with 2 decimal precision.
        currency (str): Currency code (default: "USD").
        warehouse_location (str): Warehouse location (default: "WH-A2").
        status (str): Status of the product (e.g., ACTIVE, INACTIVE).
        audits (list[InventoryAudit]): Relationship to inventory audit logs.
    """
    __tablename__ = "Inventory"

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), nullable=False)
    product_name = Column(String(255), nullable=False)
    category = Column(String(255), nullable=False)
    brand = Column(String(255), nullable=False)
    description = Column(String(255), nullable=False)
    quantity_available = Column(Integer, nullable=False)
    reorder_level = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    warehouse_location = Column(String(255), nullable=False, default="WH-A2")
    status = Column(String(20), nullable=False)

    audits = relationship("InventoryAudit", back_populates="inventory")


class InventoryAudit(Base):
    """
    Tracks changes made to inventory records.

    Attributes:
        audit_id (int): Primary key, auto-incremented audit identifier.
        product_id (int): Foreign key referencing `Inventory.product_id`.
        changeType (str): Type of change ('REMOVE' or 'UPDATE').
        quantityChanged (int): Quantity difference caused by the change.
        audittime (datetime): Timestamp of when the change occurred.
        remarks (str): Optional remarks about the change.
        inventory (Inventory): Relationship back to the related Inventory.
    """
    __tablename__ = "InventoryAudit"

    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("Inventory.product_id"), nullable=False)
    quantity_available = Column(Integer, nullable=False)
    changeType = Column(String(20), nullable=False)
    quantityChanged = Column(Integer, nullable=False)
    audittime = Column(TIMESTAMP, server_default=func.current_timestamp())
    remarks = Column(String(50))
    inventory = relationship("Inventory", back_populates="audits")


class Orders(Base):
    """
    Represents a customer order placed for products.

    Attributes:
        order_id (int): Primary key, auto-incremented order identifier.
        product_id (int): Foreign key referencing `Inventory.product_id`.
        quantity (int): Number of items ordered.
        status (str): Current status of the order
                      ('PENDING', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED').
        remarks (str): Optional remarks related to the order.
        orderDate (datetime): Timestamp of when the order was created.
        audits (list[OrderAudit]): Relationship to order audit logs.
    """
    __tablename__ = "Orders"

    order_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("Inventory.product_id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False,default="PROCESSED")
    remarks = Column(Text)
    orderDate = Column(TIMESTAMP, server_default=func.current_timestamp())
    audits = relationship("OrderAudit", back_populates="order")


class OrderAudit(Base):
    """
    Tracks changes to order statuses.

    Attributes:
        audit_id (int): Primary key, auto-incremented audit identifier.
        order_id (int): Foreign key referencing `Order.order_id`.
        previousStatus (str): Previous status of the order.
        newStatus (str): New status of the order.
        audittime (datetime): Timestamp of the status change.
        remarks (str): Optional remarks about the change.
        order (Order): Relationship back to the related Order.
    """
    __tablename__ = "OrderAudit"

    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("Orders.order_id"), nullable=False)
    previousStatus = Column(String(20), nullable=False)
    newStatus = Column(String(20), nullable=False)
    audittime = Column(TIMESTAMP, server_default=func.current_timestamp())
    remarks = Column(Text)

    order = relationship("Orders", back_populates="audits")
