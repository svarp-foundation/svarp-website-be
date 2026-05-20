import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Header
from sqlalchemy.orm import Session
from .. import crud, schemas, models
from ..database import get_db
from .auth import get_current_admin

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)

UPLOAD_DIR = "uploads/resumes"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Public Endpoints
@router.get("/", response_model=List[schemas.Job])
def list_active_jobs(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    active_only = True
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            from jose import jwt
            from .auth import SECRET_KEY, ALGORITHM
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email:
                user = crud.get_user_by_email(db, email=email)
                if user and user.role == "admin":
                    active_only = False
        except Exception:
            pass
            
    return crud.get_jobs(db, active_only=active_only)

@router.get("/{job_id}", response_model=schemas.Job)
def get_job_details(job_id: str, db: Session = Depends(get_db)):
    job = crud.get_job(db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/apply", response_model=schemas.JobApplication)
async def apply_for_job(
    job_id: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    cover_letter: Optional[str] = Form(None),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Verify job exists
    job = crud.get_job(db, job_id=job_id)
    if not job or not job.is_active:
        raise HTTPException(status_code=404, detail="Job not found or inactive")

    # Save resume
    file_extension = os.path.splitext(resume.filename)[1]
    file_name = f"{job_id}_{phone}_{resume.filename}"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(resume.file, buffer)

    application_in = schemas.JobApplicationCreate(
        job_id=job_id,
        full_name=full_name,
        email=email,
        phone=phone,
        cover_letter=cover_letter
    )
    
    return crud.create_job_application(db, application=application_in, resume_path=file_path)

# Admin Endpoints
@router.post("/", response_model=schemas.Job)
def create_new_job(
    job: schemas.JobCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    return crud.create_job(db, job=job)

@router.put("/{job_id}", response_model=schemas.Job)
def update_existing_job(
    job_id: str,
    job_update: schemas.JobUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    db_job = crud.update_job(db, job_id=job_id, job_update=job_update)
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    return db_job

@router.delete("/{job_id}")
def delete_job_post(
    job_id: str,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    success = crud.delete_job(db, job_id=job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "success"}

@router.get("/applications/all", response_model=List[schemas.JobApplication])
def list_all_applications(
    job_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    return crud.get_job_applications(db, skip=skip, limit=limit, job_id=job_id)

@router.patch("/applications/{application_id}/status", response_model=schemas.JobApplication)
def update_application_status(
    application_id: str,
    update: schemas.JobApplicationUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    db_app = crud.update_job_application_status(db, application_id=application_id, status=update.status)
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
    return db_app
