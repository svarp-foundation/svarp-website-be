from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import engine, Base
from .routers import auth, membership, donations, upload, contact, admin, jobs
import os


# Create database tables is now handled by Alembic migrations
Base.metadata.create_all(bind=engine)


def create_membership_plans():
    from .database import SessionLocal
    from . import models
    
    db = SessionLocal()
    try:
        # Check if memberships table already has plans to avoid duplicates
        existing = db.query(models.Membership).first()
        if not existing:
            print("Dumping membership plans...")
            plans = [
                models.Membership(
                    id="1",
                    name="Lifetime Membership",
                    price=25000.0,
                    features="Full access to all online & offline courses (including diplomas), Priority access to new courses & annual training calendar, Free samples of all new products & services, Invitations to premium networking events, Access to workshops, seminars & expert presentations, Exclusive discounts on certifications & premium programs, Recognized as a Lifetime Core Member, No renewals, no hassle – lifelong access, Most recommended by experts & alumni",
                    duration_days=36500  # Lifetime has no expiration date
                ),
                models.Membership(
                    id="2",
                    name="Yearly Membership",
                    price=5000.0,
                    features="Access to online courses (excluding diplomas), Free samples of select products & services, Invitations to networking meetups & events, Access to selected workshops & sessions, 1-year validity with annual renewal, Limited benefits compared to Lifetime Membership",
                    duration_days=365
                ),
                models.Membership(
                    id="3",
                    name="Student Membership",
                    price=1000.0,
                    features="All benefits of Yearly Membership, Special student discounts on diplomas & offline courses, Project recognition, awards & certifications, Career guidance & startup mentoring, Internship opportunities & real-world project exposure",
                    duration_days=365
                ),
                models.Membership(
                    id="4",
                    name="Corporate Membership",
                    price=250000.0,
                    features="Full access to all training & certification programs, R&D support and innovation assistance, Business growth, branding & expansion strategy, High-level networking & industry collaboration, HSE (Health, Safety & Sustainability) implementation support",
                    duration_days=365
                )
            ]
            db.add_all(plans)
            db.commit()
            print("Membership plans dumped successfully.")
    except Exception as e:
        print(f"Error dumping membership plans: {e}")
    finally:
        db.close()

create_membership_plans()

app = FastAPI()

@app.on_event("startup")
def startup_event():
    create_membership_plans()

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
app.include_router(jobs.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to SVARP Website Backend"}