from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db

router = APIRouter(
    prefix="/contact",
    tags=["Contact"]
)

@router.post("/", response_model=schemas.ContactMessage, status_code=status.HTTP_201_CREATED)
def create_contact_message(message: schemas.ContactMessageCreate, db: Session = Depends(get_db)):
    try:
        new_message = models.ContactMessage(**message.model_dump())
        db.add(new_message)
        db.commit()
        db.refresh(new_message)
        return new_message
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
