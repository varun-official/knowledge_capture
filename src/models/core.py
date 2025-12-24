from beanie import Document
from pydantic import Field
from datetime import datetime
from typing import Optional

class User(Document):
    username: str
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Settings:
        name = "users"

class Project(Document):
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Settings:
        name = "projects"
