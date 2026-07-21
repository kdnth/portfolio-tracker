from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.exceptions import ElementAlreadyExistsException, BadCredentialsException
from app.db.session import get_db
from app.schemas.user import UserRegister, Token, UserLogin
from app.services.auth_service import create_bearer_token
from app.services.user_service import create_user, login_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    try:
        user = create_user(payload=payload, db=db)
    except ElementAlreadyExistsException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    return create_bearer_token(user_id=user.id)

@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    try:
        user = login_user(payload=payload, db=db)
    except BadCredentialsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    return create_bearer_token(user_id=user.id)
