from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class IncomingMessage(BaseModel):
    channel: str = "manual"
    provider_message_id: Optional[str] = None
    contact_name: str
    contact_id: str
    message_text: str
    timestamp: datetime
    raw_payload: Optional[dict[str, Any]] = None


class ReviewDecisionPayload(BaseModel):
    title: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = "Medium"
    notes: Optional[str] = ""
    type: Optional[str] = None


class AISettingsPayload(BaseModel):
    enabled: bool = True
    model: str = "gemini-2.5-flash"
    confidence_threshold: float = Field(default=0.58, ge=0.0, le=1.0)
    context_messages: int = Field(default=6, ge=1, le=20)
    system_instruction: str = Field(default="")
