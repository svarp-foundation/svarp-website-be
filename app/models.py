from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, DateTime, Float, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import string
import random
from .database import Base

def generate_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

class User(Base):
    __tablename__ = "users"

    id = Column(String(8), primary_key=True, index=True, default=generate_id)
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
    
    # New fields for Membership Form
    date_of_birth = Column(Date, nullable=True)
    government_id_type = Column(String, nullable=True) # PAN, Aadhaar, Passport
    government_id_number = Column(String, nullable=True)
    government_id_path = Column(String, nullable=True)
    is_student = Column(Boolean, default=False)
    student_id_path = Column(String, nullable=True)
    profile_picture_path = Column(String, nullable=True)
    gst_number = Column(String, nullable=True)

    membership = relationship("UserMembership", back_populates="user", uselist=False)
    transactions = relationship("Transaction", back_populates="user")
    donations = relationship("Donation", back_populates="user")

class Membership(Base):
    __tablename__ = "memberships"

    id = Column(String(8), primary_key=True, index=True, default=generate_id)
    name = Column(String, unique=True)
    price = Column(Float)
    features = Column(Text) # JSON string or comma-separated list
    duration_days = Column(Integer) # 30 for monthly, 365 for yearly
    description = Column(String, nullable=True)
    highlight = Column(Boolean, default=False)

    user_memberships = relationship("UserMembership", back_populates="plan")
    transactions = relationship("Transaction", back_populates="plan")

class UserMembership(Base):
    __tablename__ = "user_memberships"

    id = Column(String(8), primary_key=True, index=True, default=generate_id)
    user_id = Column(String(8), ForeignKey("users.id"), unique=True)
    membership_id = Column(String(8), ForeignKey("memberships.id"))
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="membership")
    plan = relationship("Membership", back_populates="user_memberships")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(8), primary_key=True, index=True, default=generate_id)
    user_id = Column(String(8), ForeignKey("users.id"))
    membership_id = Column(String(8), ForeignKey("memberships.id"))
    amount = Column(Float)
    currency = Column(String, default="INR")
    status = Column(String, default="pending") # pending, success, failed
    payment_id = Column(String, nullable=True) # External payment gateway ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="transactions")
    plan = relationship("Membership", back_populates="transactions")

class Donation(Base):
    __tablename__ = "donations"

    id = Column(String(8), primary_key=True, index=True, default=generate_id)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    pan_card = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    status = Column(String, default="pending") # pending, success, failed
    payment_id = Column(String, nullable=True) # External payment gateway ID (e.g. Razorpay Order ID)
    user_id = Column(String(8), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="donations")

class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(String(8), primary_key=True, index=True, default=generate_id)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(8), primary_key=True, index=True, default=generate_id)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String, nullable=False)
    job_type = Column(String, nullable=False) # Full-time, Part-time, Internship, Freelance
    salary_range = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    applications = relationship("JobApplication", back_populates="job")

class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(String(8), primary_key=True, index=True, default=generate_id)
    job_id = Column(String(8), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    resume_path = Column(String, nullable=False)
    cover_letter = Column(Text, nullable=True)
    status = Column(String, default="pending") # pending, reviewed, interviewed, rejected, hired
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="applications")

