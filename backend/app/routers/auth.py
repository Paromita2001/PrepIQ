from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.db_models import Student
from ..schemas.pydantic_schemas import StudentCreate, StudentLogin, Token, StudentOut
from ..services.auth import hash_password, verify_password, create_token, get_current_student

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=StudentOut, status_code=201)
def register(payload: StudentCreate, db: Session = Depends(get_db)):
    if db.query(Student).filter(Student.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    student = Student(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        board=payload.board,
        exam_date=payload.exam_date,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.post("/login", response_model=Token)
def login(payload: StudentLogin, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.email == payload.email).first()
    if not student or not verify_password(payload.password, student.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": str(student.id)})
    return Token(access_token=token)


@router.get("/me", response_model=StudentOut)
def me(
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    return student
