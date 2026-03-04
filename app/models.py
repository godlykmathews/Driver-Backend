from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum, DateTime, DECIMAL
from sqlalchemy.orm import relationship
from app.database import Base
import enum
from datetime import datetime

class UserRole(enum.Enum):
    super_admin = "super_admin"
    admin = "admin"
    driver = "driver"

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    temp_password = Column(String, nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.branch_id"), nullable=True) 
    role = Column(Enum(UserRole), nullable=False)
    is_temporary = Column(Boolean, default=False)
    expiry_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    branches = relationship("DriverBranch", back_populates="driver")

class Branch(Base):
    __tablename__ = "branches"
    branch_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class DriverBranch(Base):
    __tablename__ = "driver_branches"
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.user_id"))
    branch_id = Column(Integer, ForeignKey("branches.branch_id"))
    driver = relationship("User", back_populates="branches")
    branch = relationship("Branch")

class InvoiceStatus(enum.Enum):
    pending = "pending"
    delivered = "delivered"

class Invoice(Base):
    __tablename__ = "invoices"
    invoice_id = Column(Integer, primary_key=True, index=True)
    cust_name = Column(String, nullable=False)  # Changed from shop_name to cust_name
    n_inv_no = Column(String, nullable=False)   # Added invoice number
    amount = Column(DECIMAL, nullable=False)
    invoice_date = Column(DateTime, nullable=False)  # Invoice date from CSV
    branch_id = Column(Integer, ForeignKey("branches.branch_id"))
    assigned_driver_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    status = Column(String, default="pending")  # Changed from delivery_status to status
    pdf_path = Column(String, nullable=True)
    driver_signature = Column(String, nullable=True)  # Added signature field
    driver_notes = Column(String, nullable=True)      # Added notes field
    acknowledged_at = Column(DateTime, nullable=True)  # Added acknowledgment timestamp
    delivery_date = Column(DateTime, nullable=True)
    
    # Route system fields
    route_number = Column(Integer, nullable=True)  # Sequential route number per driver per day
    route_name = Column(String, nullable=True)     # Optional custom route name
    route_date = Column(DateTime, nullable=True)   # Date when route was created (for daily reset)
    
    # Customer visit grouping - Format: "route_number-customer_name-date"
    customer_visit_group = Column(String, nullable=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DriverLocation(Base):
    __tablename__ = "driver_locations"
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.user_id"), unique=True, index=True)
    latitude = Column(DECIMAL(10, 8), nullable=False)
    longitude = Column(DECIMAL(11, 8), nullable=False)
    accuracy = Column(DECIMAL(8, 2), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

