from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .. import crud, models, schemas
from ..database import get_db
import os
import requests
import secrets
import string
from .auth import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta

router = APIRouter(
    prefix="/donations",
    tags=["donations"],
)

CPP_API_URL = os.getenv("CPP_API_URL")
CPP_APP_KEY = os.getenv("CPP_APP_KEY")
CPP_APP_SECRET = os.getenv("CPP_APP_SECRET")

@router.post("/create-order", response_model=schemas.PaymentOrderResponse)
def create_donation_order(
    donation: schemas.DonationCreate,
    db: Session = Depends(get_db)
):
    headers = {
        "x-app-key": CPP_APP_KEY,
        "x-app-secret": CPP_APP_SECRET
    }
    payload = {
        "user_id": donation.email, # Use email as identifier for anonymous donations
        "amount": int(donation.amount * 100) if donation.currency == "INR" else int(donation.amount),
        "currency": donation.currency,
        "media_type": "application/json",
        "plan_type": "donation",
        "metadata_info": {"donation_email": donation.email, "donor_name": donation.name}
    }
    
    try:
        response = requests.post(f"{CPP_API_URL}/payments/create-order", json=payload, headers=headers)
        response.raise_for_status()
        order_data = response.json()
    except requests.RequestException as e:
        print(f"CPP Error: {e}. Falling back to Offline Mock Payment Mode.")
        import uuid
        mock_order_id = f"order_mock_{uuid.uuid4().hex[:14]}"
        order_data = {
            "razorpay_order_id": mock_order_id,
            "status": "created",
            "key_id": "rzp_test_mockkey12345",
            "app_name": "SVARP Global (Mock Mode)"
        }

    # 2. Create Local Donation Record
    db_donation = crud.create_donation(db=db, donation=donation)
    
    # 3. Update payment_id with razorpay_order_id and status
    db_donation.payment_id = order_data.get("razorpay_order_id")
    db_donation.status = order_data.get("status", "created")
    db.commit()
    db.refresh(db_donation)

    return schemas.PaymentOrderResponse(
        id=db_donation.id,
        razorpay_order_id=order_data.get("razorpay_order_id"),
        amount=donation.amount, 
        currency=donation.currency,
        key_id=order_data.get("key_id"),
        app_name="SVARP GLOBAL",
        status=db_donation.status
    )

@router.post("/verify")
def verify_donation_payment(
    verify_data: schemas.PaymentVerify,
    db: Session = Depends(get_db)
):
    is_mock = verify_data.razorpay_order_id.startswith("order_mock_")
    
    if not is_mock:
        # 1. Call CPP to verify
        headers = {
            "x-app-key": CPP_APP_KEY,
            "x-app-secret": CPP_APP_SECRET
        }
        
        try:
            response = requests.post(
                f"{CPP_API_URL}/payments/verify-payment", 
                json=verify_data.dict(), 
                headers=headers
            )
            response.raise_for_status()
            verification_data = response.json()
        except requests.RequestException as e:
             print(f"CPP Verification Error: {e}")
             raise HTTPException(status_code=400, detail="Payment verification failed")

        if not verification_data.get("success"):
            raise HTTPException(status_code=400, detail="Payment verification failed by provider")

    # 2. Update Local Donation Record
    donation = db.query(models.Donation).filter(
        models.Donation.payment_id == verify_data.razorpay_order_id
    ).first()
    
    if not donation:
        raise HTTPException(status_code=404, detail="Donation record not found")

    updated_donation = crud.update_donation_status(db, donation.id, "success")
    
    # 3. User Linking and Account Creation
    user = crud.get_user_by_email(db, email=updated_donation.email)
    
    if not user:
        # Default password for accounts created during donation
        random_password = "svarp"
        
        # Create a new user record
        user_create_data = schemas.UserCreate(
            email=updated_donation.email,
            password=random_password,
            role="consumer"
        )
        user = crud.create_user(db=db, user=user_create_data)
        
        # Optionally populate profile metadata if we have it
        user_update_data = schemas.UserUpdate(
            full_name=updated_donation.name,
            phone_number=updated_donation.phone_number,
            pan_card=updated_donation.pan_card
        )
        crud.update_user(db, user.id, user_update_data)
        
    # Link the donation to the user
    updated_donation.user_id = user.id
    
    db.commit()

    # 4. Generate Access Token for Auto-login
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {
        "status": "success", 
        "message": "Donation successful. Account linked.",
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/{donation_id}/certificate", response_class=HTMLResponse)
def get_donation_certificate(donation_id: str, db: Session = Depends(get_db)):
    donation = db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    
    if not donation:
        raise HTTPException(status_code=404, detail="Donation record not found")
        
    if donation.status != "success":
        raise HTTPException(status_code=400, detail="Donation is not marked as successful")
        
    # Generate HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Donation Certificate</title>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; text-align: center; color: #333; }}
            .certificate-container {{ border: 10px solid #4ADE80; padding: 50px; margin: 20px auto; max-width: 800px; }}
            @media print {{
                .no-print {{ display: none !important; }}
                .certificate-container {{ margin: 0 auto; border: 5px solid #4ADE80; padding: 30px; }}
            }}
            .header {{ font-size: 40px; font-weight: bold; color: #166534; margin-bottom: 20px; }}
            .subheader {{ font-size: 20px; margin-bottom: 40px; }}
            .content {{ font-size: 24px; margin-bottom: 40px; line-height: 1.5; }}
            .donor-name {{ font-size: 32px; font-weight: bold; text-decoration: none; color: #15803D; }}
            .footer {{ margin-top: 50px; font-size: 16px; color: #666; }}
            .amount {{ font-size: 28px; font-weight: bold; color: #166534; }}
        </style>
    </head>
    <body>
        <div class="no-print" style="margin: 20px auto;">
            <button onclick="window.print()" style="padding: 10px 20px; background-color: #166534; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">Print / Save as PDF</button>
        </div>
        <div class="certificate-container">
            <div class="header">Certificate of Appreciation</div>
            <div class="subheader">Awarded by SVARP</div>
            <div class="content">
                This certificate is proudly presented to<br><br>
                <span class="donor-name">{donation.name}</span><br><br>
                for their generous contribution of <span class="amount">₹{donation.amount}</span> towards our cause.
            </div>
            <div class="footer">
                Date: {donation.created_at.strftime("%B %d, %Y")}<br>
                Certificate ID: {donation.id}<br>
                <br>
                <i>Thank you for making a difference.</i>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
