from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
def register(
    username: str,
    password: str,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    user = User(
        username=username,
        password_hash=hash_password(password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "User created successfully",
        "username": user.username,
    }


@router.post("/login")
def login(
    username: str,
    password: str,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if not user or not verify_password(
        password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if user.is_banned:
        raise HTTPException(
            status_code=403,
            detail="This account has been banned"
        )

    token = create_access_token(
        {
            "sub": str(user.id),
            "session_version": user.session_version,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }