from datetime import datetime, timezone
from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(254), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(10), nullable=False)
    __table_args__ = (CheckConstraint("role IN ('Admin', 'Sales')"),)


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, index=True)
    email = Column(String(254), nullable=False)
    mobile = Column(String(30), nullable=False)
    city = Column(String(100), nullable=False)
    status = Column(String(10), nullable=False, default="Active", index=True)
    __table_args__ = (CheckConstraint("status IN ('Active', 'Inactive')"),)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    product_code = Column(String(50), nullable=False, unique=True)
    name = Column(String(120), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    price = Column(Numeric(14, 2), nullable=False)
    stock_quantity = Column(Integer, nullable=False, default=0)
    status = Column(String(10), nullable=False, default="Active", index=True)
    __table_args__ = (
        CheckConstraint("price >= 0"),
        CheckConstraint("stock_quantity >= 0"),
        CheckConstraint("status IN ('Active', 'Inactive')"),
    )


class Order(Base):
    __tablename__ = "sales_orders"
    id = Column(Integer, primary_key=True)
    order_number = Column(String(40), nullable=False, unique=True)
    customer_id = Column(
        Integer, ForeignKey("customers.id"), nullable=False, index=True
    )
    order_date = Column(Date, nullable=False, index=True)
    status = Column(String(12), nullable=False, default="Draft", index=True)
    discount_percentage = Column(Numeric(5, 2), nullable=False)
    subtotal = Column(Numeric(16, 2), nullable=False)
    discount_amount = Column(Numeric(16, 2), nullable=False)
    grand_total = Column(Numeric(16, 2), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    items = relationship(
        "OrderItem", cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    __table_args__ = (
        CheckConstraint("discount_percentage BETWEEN 0 AND 20"),
        CheckConstraint("status IN ('Draft', 'Confirmed', 'Cancelled')"),
    )


class OrderItem(Base):
    __tablename__ = "sales_order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(
        Integer, ForeignKey("sales_orders.id"), nullable=False, index=True
    )
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    rate = Column(Numeric(14, 2), nullable=False)
    amount = Column(Numeric(16, 2), nullable=False)
    __table_args__ = (
        UniqueConstraint("order_id", "product_id"),
        CheckConstraint("quantity > 0"),
        CheckConstraint("rate >= 0"),
        CheckConstraint("amount >= 0"),
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    movement_type = Column(String(20), nullable=False)
    quantity_change = Column(Integer, nullable=False)
    order_id = Column(Integer, ForeignKey("sales_orders.id"), index=True)
    reason = Column(String(255), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        index=True,
    )
