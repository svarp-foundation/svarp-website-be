from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Annotated
from .. import crud, models, schemas, database
from ..database import get_db
from .auth import get_current_user

router = APIRouter(
    prefix="/memberships",
    tags=["memberships"],
)

@router.get("/", response_model=List[schemas.Membership])
def read_memberships(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    memberships = crud.get_memberships(db)
    return memberships

@router.post("/", response_model=schemas.Membership)
def create_membership(membership: schemas.MembershipCreate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    if current_user.role != "admin":
         raise HTTPException(status_code=403, detail="Not authorized")
    return crud.create_membership(db=db, membership=membership)

import os
import requests

CPP_API_URL = os.getenv("CPP_API_URL")
CPP_APP_KEY = os.getenv("CPP_APP_KEY")
CPP_APP_SECRET = os.getenv("CPP_APP_SECRET")

@router.post("/subscribe", response_model=schemas.PaymentOrderResponse)
def subscribe_to_membership(
    transaction: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    # 1. Validate Upgrade Logic
    requested_plan = db.query(models.Membership).filter(models.Membership.id == transaction.membership_id).first()
    if not requested_plan:
        raise HTTPException(status_code=404, detail="Requested membership plan not found")

    if current_user.membership and current_user.membership.is_active:
        current_plan = current_user.membership.plan
        if current_plan.id == requested_plan.id:
            raise HTTPException(status_code=400, detail="You already have an active subscription for this plan.")
        
        if requested_plan.price < current_plan.price:
            raise HTTPException(status_code=400, detail="You cannot downgrade your membership to a lower-tier plan.")

    # 2. Call CPP to create order
    # Calculate total amount with tax
    tax_rate = float(os.getenv("TAX_RATE", 18))
    calculated_tax = (requested_plan.price * tax_rate) / 100
    final_amount = requested_plan.price + calculated_tax
    transaction.amount = final_amount

    headers = {
        "x-app-key": CPP_APP_KEY,
        "x-app-secret": CPP_APP_SECRET
    }
    payload = {
        "user_id": str(current_user.id),
        "amount": int(final_amount * 100) if transaction.currency == "INR" else int(final_amount),
        "currency": transaction.currency,
        "media_type": "application/json",
        "plan_type": "membership",
        "metadata_info": {"membership_id": str(transaction.membership_id)}
    }
    
    try:
        response = requests.post(f"{CPP_API_URL}/payments/create-order", json=payload, headers=headers)
        response.raise_for_status()
        order_data = response.json()
    except requests.RequestException as e:
        print(f"CPP Error: {e}")
        raise HTTPException(status_code=502, detail="Payment Gateway unavailable")

    # 3. Create Local Transaction
    # CPP returns schema with 'id', 'razorpay_order_id', 'amount', 'currency', 'status', 'key_id'
    
    db_transaction = crud.create_transaction(db=db, transaction=transaction, user_id=current_user.id)
    
    # Update payment_id with razorpay_order_id
    db_transaction.payment_id = order_data.get("razorpay_order_id")
    # Update status to match CPP (likely 'created')
    db_transaction.status = order_data.get("status", "created")
    db.commit()
    db.refresh(db_transaction)

    return schemas.PaymentOrderResponse(
        id=db_transaction.id,
        razorpay_order_id=order_data.get("razorpay_order_id"),
        amount=transaction.amount, # Return original amount
        currency=transaction.currency,
        key_id=order_data.get("key_id"),
        app_name="SVARP", # Or from CPP if available?
        status=db_transaction.status
    )

@router.post("/verify")
def verify_payment(
    verify_data: schemas.PaymentVerify,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    # 1. Call CPP to verify
    headers = {
        "x-app-key": CPP_APP_KEY,
        "x-app-secret": CPP_APP_SECRET
    }
    # CPP expects: razorpay_order_id, razorpay_payment_id, razorpay_signature
    try:
        response = requests.post(
            f"{CPP_API_URL}/payments/verify-payment", 
            json=verify_data.dict(), 
            headers=headers
        )
        response.raise_for_status()
        # If success, returns {success: true, ...}
        verification_data = response.json()
    except requests.RequestException as e:
         print(f"CPP Verification Error: {e}")
         raise HTTPException(status_code=400, detail="Payment verification failed")

    if not verification_data.get("success"):
        raise HTTPException(status_code=400, detail="Payment verification failed by provider")

    # 2. Update Local Transaction
    # Find transaction by order_id (stored in payment_id)
    transaction = db.query(models.Transaction).filter(
        models.Transaction.payment_id == verify_data.razorpay_order_id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Use our CRUD function to update status and activate membership
    updated_transaction = crud.update_transaction_status(db, transaction.id, "success")
    
    return {"status": "success", "message": "Membership activated"}

@router.put("/transactions/{transaction_id}", response_model=schemas.Transaction)
def update_transaction(
    transaction_id: str,
    status: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    # Admin only or specific logic
    if current_user.role != "admin":
         raise HTTPException(status_code=403, detail="Not authorized")
         
    updated_transaction = crud.update_transaction_status(db, transaction_id, status)
    if not updated_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return updated_transaction
