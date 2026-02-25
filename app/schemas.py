from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List, Union
from datetime import datetime

# User Schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "consumer"

class UserLogin(UserBase):
    password: str

class UserMembership(BaseModel):
    id: int
    membership_id: int
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

class User(UserBase):
    id: int
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
    id: int

    model_config = ConfigDict(from_attributes=True)

# Transaction Schemas
class TransactionBase(BaseModel):
    membership_id: int
    amount: float
    currency: str = "INR"
    payment_id: Optional[str] = None

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    id: int
    user_id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PaymentVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class PaymentOrderResponse(BaseModel):
    id: Union[int, str] # Local transaction ID
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
    user_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
