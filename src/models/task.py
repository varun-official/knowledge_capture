from beanie import Document
from pydantic import Field
from datetime import datetime
from typing import Optional

class Task(Document):
    type: str # ingestion
    payload: dict
    status: str = "pending"
    worker_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Settings:
        name = "tasks"
