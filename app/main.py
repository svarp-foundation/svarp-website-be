from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import engine, Base
from .routers import auth, membership, donations, upload, contact
import os

# Create database tables
Base.metadata.create_all(bind=engine)

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

@app.get("/")
def read_root():
    return {"message": "Welcome to SVARP Website Backend"}