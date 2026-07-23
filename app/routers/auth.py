from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..clients.user_portal_client import user_portal_client, ServiceError
from .. import models, schemas
from ..database import get_db

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> schemas.User:
    """
    Validate token via portal-user, fetch user info, and auto-sync a lightweight
    local User record for FK integrity (memberships, transactions, donations).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        validation = await user_portal_client.validate_token(token)
        if not validation.get("is_valid"):
            raise credentials_exception

        user_id = str(validation.get("user_id"))
        user_info = await user_portal_client.get_user(user_id=user_id)

        roles = user_info.get("roles", [])
        primary_role = "admin" if "admin" in roles else "consumer"

        if not user_info.get("is_active", True):
            raise HTTPException(status_code=400, detail="Inactive user")

        email = user_info.get("email")
        full_name = user_info.get("full_name") or (email.split("@")[0].title() if email else "")

        # Auto-sync with local DB for FK integrity
        db_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not db_user and email:
            db_user = db.query(models.User).filter(models.User.email == email).first()

        if db_user:
            db_user.id = user_id
            db_user.email = email
            db_user.full_name = full_name
            db_user.role = primary_role
            db_user.is_active = True
            db.commit()
            db.refresh(db_user)
        else:
            db_user = models.User(
                id=user_id,
                email=email,
                full_name=full_name,
                role=primary_role,
                is_active=True,
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)

        return schemas.User(
            id=user_id,
            email=email,
            is_active=True,
            role=primary_role,
            created_at=db_user.created_at if (db_user and db_user.created_at) else datetime.utcnow(),
            full_name=db_user.full_name,
            phone_number=db_user.phone_number,
            pan_card=db_user.pan_card,
            adhaar_card=db_user.adhaar_card,
            address=db_user.address,
            city=db_user.city,
            state=db_user.state,
            pincode=db_user.pincode,
            date_of_birth=db_user.date_of_birth,
            government_id_type=db_user.government_id_type,
            government_id_number=db_user.government_id_number,
            government_id_path=db_user.government_id_path,
            is_student=db_user.is_student,
            student_id_path=db_user.student_id_path,
            profile_picture_path=db_user.profile_picture_path,
            gst_number=db_user.gst_number,
            verification_status=db_user.verification_status or "unverified",
            verification_reason=db_user.verification_reason,
            membership=db_user.membership,
            transactions=db_user.transactions or [],
            donations=db_user.donations or [],
        )
    except ServiceError as se:
        raise HTTPException(status_code=se.status_code, detail=se.detail)
    except HTTPException:
        raise
    except Exception:
        raise credentials_exception


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[schemas.User]:
    if not token:
        return None
    try:
        return await get_current_user(token, db)
    except Exception:
        return None


async def get_current_admin(current_user: schemas.User = Depends(get_current_user)) -> schemas.User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges",
        )
    return current_user


@router.post("/register", response_model=schemas.User)
async def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user via portal-user, then sync a local record."""
    try:
        full_name = user.full_name or user.email.split("@")[0].title()
        portal_user = await user_portal_client.create_user(
            email=user.email,
            password=user.password,
            full_name=full_name,
        )
        roles = portal_user.get("roles", [])
        primary_role = "admin" if "admin" in roles else "consumer"
        portal_user_id = str(portal_user.get("user_id"))

        # Sync local record
        db_user = db.query(models.User).filter(models.User.email == user.email).first()
        if not db_user:
            db_user = models.User(
                id=portal_user_id,
                email=user.email,
                full_name=full_name,
                role=primary_role,
                is_active=True,
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
        else:
            db_user.id = portal_user_id
            db_user.full_name = full_name
            db_user.role = primary_role
            db.commit()
            db.refresh(db_user)

        return schemas.User(
            id=portal_user_id,
            email=user.email,
            full_name=portal_user.get("full_name") or full_name,
            role=primary_role,
            is_active=True,
            created_at=db_user.created_at if db_user.created_at else datetime.utcnow(),
        )
    except ServiceError as se:
        # Check if the user already exists on the portal
        try:
            existing_user = await user_portal_client.get_user(email=user.email)
            if existing_user and existing_user.get("user_id"):
                roles = existing_user.get("roles", [])
                primary_role = "admin" if "admin" in roles else "consumer"
                return schemas.User(
                    id=str(existing_user.get("user_id")),
                    email=existing_user.get("email"),
                    full_name=existing_user.get("full_name") or user.email.split("@")[0].title(),
                    role=primary_role,
                    is_active=True,
                    created_at=datetime.utcnow(),
                )
        except Exception:
            pass

        if se.status_code == 400:
            raise HTTPException(status_code=400, detail="This email is already registered. Please log in.")
        raise HTTPException(status_code=se.status_code, detail=se.detail)
    except Exception:
        raise HTTPException(status_code=400, detail="Registration could not be completed. Please try logging in or use another email.")


@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate via portal-user and return the portal's JWT."""
    try:
        auth_res = await user_portal_client.login(
            email=form_data.username,
            password=form_data.password,
        )
        return {
            "access_token": auth_res.get("access_token"),
            "token_type": auth_res.get("token_type", "bearer"),
        }
    except ServiceError as se:
        raise HTTPException(status_code=se.status_code, detail=se.detail)


@router.get("/me", response_model=schemas.User)
async def read_users_me(current_user: schemas.User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=schemas.User)
async def update_user_me(
    user_update: schemas.UserUpdate,
    current_user: schemas.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update local profile fields. Sync shared fields (full_name) to portal-user."""
    db_user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)

    if db_user.government_id_path and db_user.verification_status in [None, "unverified", "rejected"]:
        db_user.verification_status = "pending"

    db.commit()
    db.refresh(db_user)

    # Sync shared fields to portal-user
    portal_update = {}
    if "full_name" in update_data:
        portal_update["full_name"] = update_data["full_name"]
    if portal_update:
        try:
            await user_portal_client.update_user(current_user.id, portal_update)
        except ServiceError:
            pass  # Non-critical: local update succeeded

    return db_user
