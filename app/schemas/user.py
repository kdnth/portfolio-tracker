from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime

class UserRegister(BaseModel):
    username: str = Field(min_length=5)
    email: EmailStr
    password: str = Field(min_length=8)

class UserLogin(BaseModel):
    identifier: str
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: EmailStr
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str
