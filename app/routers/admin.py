import os
from fastapi import APIRouter, Depends, Query, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from .. import crud, schemas
from ..database import get_db

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
        profile_picture_path=user.profile_picture_path,
        membership=user.membership,
        documents=documents,
        payment_readiness=payment_readiness,
    )
