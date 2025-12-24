from beanie import Document
from pydantic import Field
from datetime import datetime
from typing import Optional, List, Dict, Any

class FileMetadata(Document):
    project_id: str
    filename: str
    gridfs_id: str
    file_size: int
    content_type: str
    status: str = "pending"
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Settings:
        name = "files"

class Chunk(Document):
    document_id: str # Ref to FileMetadata
    project_id: str
    chunk_index: int
    content: str
    embedding: List[float] # Voyage-3 (1024 dims)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Settings:
        name = "chunks"
