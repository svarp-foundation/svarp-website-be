from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="consumer") # consumer, admin
    full_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    pan_card = Column(String, nullable=True)
    adhaar_card = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    pincode = Column(String, nullable=True)

    membership = relationship("UserMembership", back_populates="user", uselist=False)
    transactions = relationship("Transaction", back_populates="user")
    donations = relationship("Donation", back_populates="user")

class Membership(Base):
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    price = Column(Float)
    features = Column(Text) # JSON string or comma-separated list
    duration_days = Column(Integer) # 30 for monthly, 365 for yearly

    user_memberships = relationship("UserMembership", back_populates="plan")
    transactions = relationship("Transaction", back_populates="plan")

class UserMembership(Base):
    __tablename__ = "user_memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    membership_id = Column(Integer, ForeignKey("memberships.id"))
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="membership")
    plan = relationship("Membership", back_populates="user_memberships")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    membership_id = Column(Integer, ForeignKey("memberships.id"))
    amount = Column(Float)
    currency = Column(String, default="INR")
    status = Column(String, default="pending") # pending, success, failed
    payment_id = Column(String, nullable=True) # External payment gateway ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="transactions")
    plan = relationship("Membership", back_populates="transactions")

class Donation(Base):
    __tablename__ = "donations"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    pan_card = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    status = Column(String, default="pending") # pending, success, failed
    payment_id = Column(String, nullable=True) # External payment gateway ID (e.g. Razorpay Order ID)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="donations")
