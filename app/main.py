from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import engine, Base
from .routers import auth, membership, donations, upload, contact, admin
import os


# Create database tables is now handled by Alembic migrations
# Base.metadata.create_all(bind=engine)

def create_admin_user():
    from .database import SessionLocal
    from . import crud, schemas
    import os
    
    db = SessionLocal()
    try:
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")
        
        if admin_email and admin_password:
            db_user = crud.get_user_by_email(db, email=admin_email)
            if not db_user:
                print(f"Creating admin user: {admin_email}")
                admin_in = schemas.UserCreate(
                    email=admin_email,
                    password=admin_password,
                    role="admin"
                )
                crud.create_user(db, admin_in)
            else:
                # Optionally update password if changed in .env
                if not crud.verify_password(admin_password, db_user.hashed_password):
                    print(f"Updating admin password for: {admin_email}")
                    db_user.hashed_password = crud.get_password_hash(admin_password)
                    db_user.role = "admin" # Ensure role is admin
                    db.commit()
    finally:
        db.close()

create_admin_user()

app = FastAPI()

if not os.path.exists("uploads"):
    os.makedirs("uploads")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# CORS configuration
origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(membership.router)
app.include_router(donations.router)
app.include_router(upload.router)
app.include_router(contact.router)
app.include_router(admin.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to SVARP Website Backend"}