from pydantic import BaseModel


class GoogleLoginURL(BaseModel):
    authorization_url: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
