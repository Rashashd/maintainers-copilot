import uuid
from datetime import datetime

from pydantic import BaseModel


class MemoryEntryRead(BaseModel):
    id: uuid.UUID
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
