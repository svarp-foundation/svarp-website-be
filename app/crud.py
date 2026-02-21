from sqlalchemy.orm import Session
from . import models, schemas
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None
    
    update_data = user_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

def get_memberships(db: Session):
    return db.query(models.Membership).all()

def create_membership(db: Session, membership: schemas.MembershipCreate):
    db_membership = models.Membership(**membership.dict())
    db.add(db_membership)
    db.commit()
    db.refresh(db_membership)
    return db_membership

def create_transaction(db: Session, transaction: schemas.TransactionCreate, user_id: int):
    db_transaction = models.Transaction(
        **transaction.dict(),
        user_id=user_id,
        status="pending"
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

def update_transaction_status(db: Session, transaction_id: int, status: str):
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not transaction:
        return None
    
    transaction.status = status
    db.commit()
    db.refresh(transaction)

    if status == "success":
        # Activate Membership Logic
        from datetime import datetime, timedelta
        
    # Get plan details for duration
    plan = db.query(models.Membership).filter(models.Membership.id == transaction.membership_id).first()
    if not plan:
        print(f"ERROR: Membership plan {transaction.membership_id} not found for transaction {transaction_id}. UserMembership NOT created.")
    
    if plan:
            duration = plan.duration_days
            start_date = datetime.now()
            end_date = start_date + timedelta(days=duration) if duration else None

            # Check if user already has a membership record
            user_membership = db.query(models.UserMembership).filter(models.UserMembership.user_id == transaction.user_id).first()

            if user_membership:
                # Update existing
                user_membership.membership_id = transaction.membership_id
                user_membership.start_date = start_date
                user_membership.end_date = end_date
                user_membership.is_active = True
            else:
                # Create new
                user_membership = models.UserMembership(
                    user_id=transaction.user_id,
                    membership_id=transaction.membership_id,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True
                )
                db.add(user_membership)
            
            db.commit()

    return transaction
