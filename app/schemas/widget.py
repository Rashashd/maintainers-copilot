import uuid
from datetime import datetime

from pydantic import BaseModel


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
