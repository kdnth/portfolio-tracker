from sqlalchemy.orm import Session

from app.core.exceptions import NoSuchElementException, ElementAlreadyExistsException, BadCredentialsException
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserRegister, UserLogin


def create_user(payload: UserRegister, db: Session) -> User:
    """Creates new user in DB from the provided payload. Returns created User. Raises ElementAlreadyExistsException if username or email already exist"""
    if user_exists_with_username_or_email(username=payload.username, email=payload.email, db=db):
        raise ElementAlreadyExistsException()

    user = User(username=payload.username, email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def login_user(payload: UserLogin, db: Session,) -> User:
    """Queries DB for user with matching identifier. Returns matching User. Raises BadCredentialsException if the user does not exist or password is incorrect"""
    try:
        user = get_user_by_identifier(identifier=payload.identifier, db=db)
    except NoSuchElementException:
        raise BadCredentialsException()

    if not verify_password(payload.password, user.password_hash):
        raise BadCredentialsException()

    return user

def get_user_by_identifier(identifier: str, db: Session) -> User:
    """Queries DB for user where username or email matches identifier. Returns matching User. Raises NoSuchElementException if user is not found."""
    user = db.query(User).filter(
        (User.username == identifier) | (User.email == identifier)
    ).first()
    if user is None:
        raise NoSuchElementException()
    return user

def user_exists_with_username_or_email(username: str, email: str, db: Session) -> bool:
    """Queries DB for user with matching email or username. Returns true if found, false if not. Exists to avoid two round trips to DB when registering a new user."""
    return db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first() is not None