from app.core.security import create_access_token
from app.schemas.user import Token


def create_bearer_token(user_id: int) -> Token:
    """Creates access token from user_id and returns new bearer Token"""
    access_token = create_access_token(subject=str(user_id))
    return Token(access_token=access_token, token_type="bearer")