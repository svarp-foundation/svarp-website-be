import os
import csv
import io
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Response, status, Header, Security, UploadFile, File
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from dotenv import load_dotenv
from .. import crud, schemas, models
from ..database import get_db
from .auth import get_current_admin
from ..clients.user_portal_client import user_portal_client, ServiceError

load_dotenv()

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Validate the API key from the X-API-Key header."""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


@router.get("/verify-user", response_model=schemas.UserVerificationResponse)
def verify_user_by_email(
    email: str = Query(..., description="Email address to look up"),
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    """
    Look up a user by email and return:
    - Whether the user exists
    - Current membership details
    - Which documents have been uploaded (true/false)
    - Whether all required documents/fields for payment are ready

    Requires a valid API key in the X-API-Key header.
    """
    user = crud.get_user_by_email(db, email=email)

    if not user:
        return schemas.UserVerificationResponse(found=False)

    documents = schemas.UserDocuments(
        has_government_id=bool(user.government_id_path),
        has_student_id=bool(user.student_id_path),
        has_profile_picture=bool(user.profile_picture_path),
    )

    # Check all required fields for payment
    has_full_name = bool(user.full_name and user.full_name.strip())
    has_phone_number = bool(user.phone_number and user.phone_number.strip())
    has_pan_card = bool(user.pan_card and user.pan_card.strip())
    has_address = bool(user.address and user.address.strip())
    has_city = bool(user.city and user.city.strip())
    has_state = bool(user.state and user.state.strip())
    has_gov_doc = bool(user.government_id_path)
    has_profile_pic = bool(user.profile_picture_path)

    all_ready = all([
        has_full_name, has_phone_number, has_pan_card,
        has_address, has_city, has_state,
        has_gov_doc, has_profile_pic,
    ])

    payment_readiness = schemas.PaymentReadiness(
        ready=all_ready,
        has_full_name=has_full_name,
        has_phone_number=has_phone_number,
        has_pan_card=has_pan_card,
        has_address=has_address,
        has_city=has_city,
        has_state=has_state,
        has_government_id_doc=has_gov_doc,
        has_profile_picture_doc=has_profile_pic,
    )

    return schemas.UserVerificationResponse(
        found=True,
        phone_number=user.phone_number,
        profile_picture_path=user.profile_picture_path,
        membership=user.membership,
        documents=documents,
        payment_readiness=payment_readiness,
    )


# 1. Overview Dashboard
@router.get("/stats", response_model=schemas.AdminDashboardStats)
def get_admin_stats(
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    """Show key metrics and chart data."""
    total_users = db.query(models.User).count()
    active_users = db.query(models.User).filter(models.User.is_active == True).count()
    
    total_revenue = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.status == "success"
    ).scalar() or 0.0
    
    pending_verifications = db.query(models.User).filter(
        models.User.government_id_path != None,
        models.User.verification_status == "pending"
    ).count()

    # Monthly revenue trends
    monthly_revenue_data = db.query(
        func.strftime('%Y-%m', models.Transaction.created_at).label('month'),
        func.sum(models.Transaction.amount).label('revenue')
    ).filter(models.Transaction.status == "success").group_by('month').order_by('month').all()
    
    monthly_rev_list = [{"month": r.month, "revenue": r.revenue} for r in monthly_revenue_data]

    # Monthly users trends
    monthly_users_data = db.query(
        func.strftime('%Y-%m', models.User.created_at).label('month'),
        func.count(models.User.id).label('count')
    ).filter(models.User.created_at != None).group_by('month').order_by('month').all()
    
    monthly_users_list = [{"month": r.month, "count": r.count} for r in monthly_users_data]
    
    return schemas.AdminDashboardStats(
        total_users=total_users,
        active_users=active_users,
        total_revenue=total_revenue,
        pending_verifications=pending_verifications,
        monthly_revenue=monthly_rev_list,
        monthly_users=monthly_users_list
    )


# 2. User Management
@router.get("/users", response_model=List[schemas.User])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    try:
        portal_users = await user_portal_client.list_users(skip=skip, limit=limit, search=search)
    except Exception as e:
        portal_users = []

    result = []
    for pu in portal_users:
        user_id = str(pu.get("user_id"))
        email = pu.get("email")
        full_name = pu.get("full_name") or (email.split("@")[0].title() if email else "")
        roles = pu.get("roles", [])
        primary_role = "admin" if "admin" in roles else "consumer"
        is_active = pu.get("is_active", True)

        if status == "active" and not is_active:
            continue
        if status == "suspended" and is_active:
            continue

        # Sync/get local record for profile & membership data
        db_user = crud.sync_user_from_portal(
            db,
            user_id=user_id,
            email=email,
            full_name=full_name,
            role=primary_role,
        )
        db_user.is_active = is_active
        db.commit()

        result.append(db_user)

    return result


@router.get("/users/{user_id}", response_model=schemas.User)
async def get_user_details(
    user_id: str,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        try:
            pu = await user_portal_client.get_user(user_id=user_id)
            if pu and pu.get("user_id"):
                email = pu.get("email")
                full_name = pu.get("full_name") or (email.split("@")[0].title() if email else "")
                roles = pu.get("roles", [])
                primary_role = "admin" if "admin" in roles else "consumer"
                db_user = crud.sync_user_from_portal(db, user_id=str(pu["user_id"]), email=email, full_name=full_name, role=primary_role)
        except Exception:
            pass
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.put("/users/{user_id}", response_model=schemas.User)
async def update_user_admin(
    user_id: str,
    update: schemas.AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    update_data = update.dict(exclude_unset=True)
    portal_update = {}
    for key, value in update_data.items():
        if key == "membership_plan_id" and value:
            pass
        else:
            setattr(db_user, key, value)
            if key in ("full_name", "is_active"):
                portal_update[key] = value
            
    db.commit()
    db.refresh(db_user)

    # Sync shared fields to portal-user
    if portal_update:
        try:
            await user_portal_client.update_user(user_id, portal_update)
        except ServiceError:
            pass  # Non-critical: local update succeeded

    return db_user


@router.patch("/users/{user_id}/status")
async def toggle_user_status(
    user_id: str,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.is_active = not db_user.is_active
    db.commit()

    # Sync to portal-user
    try:
        await user_portal_client.update_user(user_id, {"is_active": db_user.is_active})
    except ServiceError:
        pass

    return {"status": "success", "is_active": db_user.is_active}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.query(models.UserMembership).filter(models.UserMembership.user_id == user_id).delete()
    db.query(models.Transaction).filter(models.Transaction.user_id == user_id).delete()
    db.delete(db_user)
    db.commit()
    return {"status": "success"}


# 3. Membership Management
@router.post("/memberships/assign")
def assign_membership(
    assignment: schemas.MembershipAssignment,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    user_id = assignment.user_id
    membership_id = assignment.membership_id
    duration_days = assignment.duration_days
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    plan = db.query(models.Membership).filter(models.Membership.id == membership_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Membership plan not found")
    
    start_date = datetime.now()
    end_date = start_date + timedelta(days=duration_days)
    
    user_membership = db.query(models.UserMembership).filter(models.UserMembership.user_id == user_id).first()
    if user_membership:
        user_membership.membership_id = membership_id
        user_membership.start_date = start_date
        user_membership.end_date = end_date
        user_membership.is_active = True
    else:
        user_membership = models.UserMembership(
            user_id=user_id,
            membership_id=membership_id,
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )
        db.add(user_membership)
    
    db.commit()
    return {"status": "success"}


@router.post("/memberships/cancel/{user_id}")
def cancel_membership(
    user_id: str,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    user_membership = db.query(models.UserMembership).filter(models.UserMembership.user_id == user_id).first()
    if not user_membership:
        raise HTTPException(status_code=404, detail="Membership not found for this user")
    
    user_membership.is_active = False
    db.commit()
    return {"status": "success"}


# 4. Payment Management
@router.get("/payments", response_model=List[schemas.Transaction])
def list_payments(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    query = db.query(models.Transaction)
    if status:
        query = query.filter(models.Transaction.status == status)
    return query.order_by(desc(models.Transaction.created_at)).offset(skip).limit(limit).all()


@router.get("/payments/export")
def export_payments(
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    transactions = db.query(models.Transaction).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "User ID", "Membership ID", "Amount", "Status", "Payment ID", "Created At"])
    
    for tx in transactions:
        writer.writerow([tx.id, tx.user_id, tx.membership_id, tx.amount, tx.status, tx.payment_id, tx.created_at])
        
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=payments_{datetime.now().strftime('%Y%m%d')}.csv"}
    )


@router.get("/verifications", response_model=List[schemas.User])
def list_verifications(
    status: str = "pending",
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    return db.query(models.User).filter(
        models.User.government_id_path != None,
        models.User.verification_status == status
    ).all()


@router.post("/verifications/{user_id}/review")
def review_verification(
    user_id: str,
    review: schemas.VerificationReview,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db_user.verification_status = review.status
    db_user.verification_reason = review.reason if review.status == "rejected" else None
    db.commit()
    db.refresh(db_user)
        
    return {"status": "success", "message": f"User verification {review.status}"}


@router.post("/users/bulk-import", response_model=schemas.BulkImportResponse)
async def bulk_import_users(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    """
    Import users in bulk via a CSV file.
    Creates users on portal-user first, then syncs local profile records.
    All imported users will have their role set to 'consumer' by default.
    Skipped rows are returned with detailed error messages.
    """
    import re
    contents = await file.read()
    try:
        decoded = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file encoding. Please upload a UTF-8 encoded CSV file."
        )
    
    f = io.StringIO(decoded)
    reader = csv.reader(f)
    
    try:
        headers = next(reader)
    except StopIteration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty."
        )
    
    email_idx = -1
    password_idx = -1
    fullname_idx = -1
    phone_idx = -1
    
    for i, h in enumerate(headers):
        h_norm = h.strip().lower().replace("_", "").replace(" ", "").replace("-", "")
        if h_norm in ("email", "username", "emailaddress"):
            email_idx = i
        elif h_norm in ("password", "pass"):
            password_idx = i
        elif h_norm in ("fullname", "name", "namefull", "usernamefull"):
            fullname_idx = i
        elif h_norm in ("phone", "phonenumber", "mobile", "mobilenumber", "contact", "contactnumber"):
            phone_idx = i

    if email_idx == -1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain an 'email' column."
        )
    if password_idx == -1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain a 'password' column."
        )

    success_count = 0
    errors = []
    processed_emails = set()
    email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    
    for row_num, row in enumerate(reader, start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        
        email = row[email_idx].strip() if email_idx < len(row) else ""
        password = row[password_idx].strip() if password_idx < len(row) else ""
        fullname = row[fullname_idx].strip() if (fullname_idx != -1 and fullname_idx < len(row)) else None
        phone = row[phone_idx].strip() if (phone_idx != -1 and phone_idx < len(row)) else None
        
        if not email:
            errors.append(schemas.BulkImportError(row=row_num, email=None, error="Email is required."))
            continue
            
        if not password:
            errors.append(schemas.BulkImportError(row=row_num, email=email, error="Password is required."))
            continue
            
        if len(password) < 6:
            errors.append(schemas.BulkImportError(row=row_num, email=email, error="Password must be at least 6 characters long."))
            continue
            
        if not re.match(email_regex, email):
            errors.append(schemas.BulkImportError(row=row_num, email=email, error="Invalid email format."))
            continue
            
        if email.lower() in processed_emails:
            errors.append(schemas.BulkImportError(row=row_num, email=email, error="Duplicate email in the CSV file."))
            continue
            
        existing_user = db.query(models.User).filter(models.User.email == email).first()
        if existing_user:
            errors.append(schemas.BulkImportError(row=row_num, email=email, error="Email already registered."))
            continue
            
        try:
            # Create user on portal-user first
            portal_user = await user_portal_client.create_user(
                email=email,
                password=password,
                full_name=fullname or email.split("@")[0].title(),
            )
            portal_user_id = str(portal_user.get("user_id"))

            # Sync local profile record
            db_user = crud.sync_user_from_portal(
                db,
                user_id=portal_user_id,
                email=email,
                full_name=fullname,
                role="consumer",
            )
            # Store phone locally if provided
            if phone:
                db_user.phone_number = phone
                db.commit()

            processed_emails.add(email.lower())
            success_count += 1
        except ServiceError as se:
            errors.append(schemas.BulkImportError(row=row_num, email=email, error=f"Portal error: {se.detail}"))
        except Exception as e:
            db.rollback()
            errors.append(schemas.BulkImportError(row=row_num, email=email, error=f"Error: {str(e)}"))
            
    return schemas.BulkImportResponse(
        successful_count=success_count,
        failed_count=len(errors),
        errors=errors
    )

