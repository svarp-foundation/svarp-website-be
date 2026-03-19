from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List, Union
from datetime import datetime, date

# User Schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "consumer"

class UserLogin(UserBase):
    password: str

class UserMembership(BaseModel):
    id: str
    membership_id: str
    start_date: datetime
    end_date: Optional[datetime]
    is_active: bool
    plan: 'Membership' # Forward reference

    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    pan_card: Optional[str] = None
    adhaar_card: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    date_of_birth: Optional[date] = None
    government_id_type: Optional[str] = None
    government_id_number: Optional[str] = None
    government_id_path: Optional[str] = None
    is_student: Optional[bool] = None
    student_id_path: Optional[str] = None
    profile_picture_path: Optional[str] = None
    gst_number: Optional[str] = None

class User(UserBase):
    id: str
    is_active: bool
    role: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    pan_card: Optional[str] = None
    adhaar_card: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    date_of_birth: Optional[date] = None
    government_id_type: Optional[str] = None
    government_id_number: Optional[str] = None
    government_id_path: Optional[str] = None
    is_student: Optional[bool] = None
    student_id_path: Optional[str] = None
    profile_picture_path: Optional[str] = None
    gst_number: Optional[str] = None
    membership: Optional[UserMembership] = None
    transactions: List['Transaction'] = []
    donations: List['Donation'] = []

    model_config = ConfigDict(from_attributes=True)

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Membership Schemas
class MembershipBase(BaseModel):
    name: str
    price: float
    features: str
    duration_days: Optional[int] = None

class MembershipCreate(MembershipBase):
    pass

class Membership(MembershipBase):
    id: str

    model_config = ConfigDict(from_attributes=True)

# Transaction Schemas
class TransactionBase(BaseModel):
    membership_id: str
    amount: float
    currency: str = "INR"
    payment_id: Optional[str] = None

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    id: str
    user_id: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PaymentVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class PaymentOrderResponse(BaseModel):
    id: str # Local transaction ID
    razorpay_order_id: str
    amount: float
    currency: str
    key_id: str # Razorpay Key ID from CPP
    app_name: str # App Name from CPP
    status: str

# Donation Schemas
class DonationBase(BaseModel):
    name: str
    email: EmailStr
    phone_number: str
    pan_card: Optional[str] = None
    amount: float
    currency: str = "INR"

class DonationCreate(DonationBase):
    pass

class Donation(DonationBase):
    id: str
    status: str
    payment_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: datetime

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Contact Message Schemas
class ContactMessageBase(BaseModel):
    name: str
    email: EmailStr
    message: str

class ContactMessageCreate(ContactMessageBase):
    pass

class ContactMessage(ContactMessageBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# User Verification Schemas
class UserDocuments(BaseModel):
    has_government_id: bool = False
    has_student_id: bool = False
    has_profile_picture: bool = False

class PaymentReadiness(BaseModel):
    ready: bool = False
    has_full_name: bool = False
    has_phone_number: bool = False
    has_pan_card: bool = False
    has_address: bool = False
    has_city: bool = False
    has_state: bool = False
    has_government_id_doc: bool = False
    has_profile_picture_doc: bool = False

class UserVerificationResponse(BaseModel):
    found: bool
    phone_number: Optional[str] = None
    profile_picture_path: Optional[str] = None
    membership: Optional[UserMembership] = None
    documents: Optional[UserDocuments] = None
    payment_readiness: Optional[PaymentReadiness] = None

# Admin Specific Schemas
class AdminDashboardStats(BaseModel):
    total_users: int
    active_users: int
    total_revenue: float
    pending_verifications: int
    monthly_revenue: List[dict] # {month: str, revenue: float}
    monthly_users: List[dict] # {month: str, count: int}

class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None
    membership_plan_id: Optional[str] = None

class VerificationReview(BaseModel):
    status: str # approved, rejected
    reason: Optional[str] = None

class MembershipAssignment(BaseModel):
    user_id: str
    membership_id: str
    duration_days: int = 365
