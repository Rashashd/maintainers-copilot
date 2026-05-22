import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WidgetChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class WidgetChatResponse(BaseModel):
    reply: str
    session_id: str


class WidgetCreate(BaseModel):
    name: str
    allowed_origins: list[str] = []
    theme: dict = {}
    greeting: str = "How can I help you?"
    enabled_tools: list[str] = []


class WidgetUpdate(BaseModel):
    name: str | None = None
    allowed_origins: list[str] | None = None
    theme: dict | None = None
    greeting: str | None = None
    enabled_tools: list[str] | None = None


class WidgetRead(BaseModel):
    id: uuid.UUID
    name: str
    allowed_origins: list[str]
    theme: dict
    greeting: str
    enabled_tools: list[str]
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
