from fastapi import APIRouter, UploadFile, File, Form, Depends
from src.services.storage import StorageService
from src.services.queue import QueueService
from src.models.files import FileMetadata
from typing import List

router = APIRouter(prefix="/files", tags=["Files"])

@router.post("/upload")
async def upload_file(project_id: str = Form(...), file: UploadFile = File(...)):
    # 1. Store
    gridfs_id = await StorageService.upload_file(file, metadata={"project_id": project_id})
    
    # 2. Meta
    file_doc = FileMetadata(
        project_id=project_id,
        filename=file.filename,
        gridfs_id=str(gridfs_id),
        file_size=file.size or 0,
        content_type=file.content_type,
        status="pending"
    )
    await file_doc.insert()
    
    # 3. Queue
    await QueueService.push_task("ingestion", {"file_id": str(file_doc.id)})
    
    return {"message": "Queued", "file_id": str(file_doc.id)}
