from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    username: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatInput(BaseModel):
    question: str = Field(min_length=1, max_length=8000)


class Usage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatOutput(BaseModel):
    answer: str
    request_id: str
    latency_ms: int
    usage: Usage


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
