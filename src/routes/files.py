from fastapi import APIRouter, UploadFile, File, Form, Depends
from pydantic import BaseModel
from src.services.storage import StorageService
from src.services.queue import QueueService
from src.models.files import FileMetadata, Chunk
from typing import List

router = APIRouter(prefix="/files", tags=["Files"])

@router.post("/upload")
async def upload_file(
    user_email: str = Form(...),
    file: UploadFile = File(...)
):
    # 1. Store
    # Use user_email as the corpus identifier
    gridfs_id = await StorageService.upload_file(file, metadata={"user_corpus": user_email, "user_email": user_email})
    
    # 2. Meta
    file_doc = FileMetadata(
        user_corpus=user_email,
        user_email=user_email,
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

class QAPair(BaseModel):
    question: str
    answer: str

class QAIngestRequest(BaseModel):
    user_email: str
    heading: str = "Q&A Session"
    qa_pairs: List[QAPair]

@router.post("/ingest-qa")
async def ingest_qa_pairs(request: QAIngestRequest):
    # 1. Generate Markdown content
    md_content = f"# {request.heading}\n\n"
    for pair in request.qa_pairs:
        md_content += f"## Q: {pair.question}\n{pair.answer}\n\n"
    
    file_bytes = md_content.encode('utf-8')
    filename = f"qa_session_{request.heading.lower().replace(' ', '_')}.md"
    
    # 2. Store
    gridfs_id = await StorageService.upload_bytes(
        filename=filename, 
        content=file_bytes, 
        metadata={"user_corpus": request.user_email, "user_email": request.user_email}
    )
    
    # 3. Meta
    file_doc = FileMetadata(
        user_corpus=request.user_email,
        user_email=request.user_email,
        filename=filename,
        gridfs_id=str(gridfs_id),
        file_size=len(file_bytes),
        content_type="text/markdown",
        status="pending"
    )
    await file_doc.insert()
    
    # 4. Queue
    await QueueService.push_task("ingestion", {"file_id": str(file_doc.id)})
    
    return {"message": "Queued Q&A Ingestion", "file_id": str(file_doc.id)}

@router.get("/list")
async def list_files(user_email: str):
    files = await FileMetadata.find(FileMetadata.user_email == user_email).sort("-created_at").to_list()
    return list(files)

@router.delete("/{file_id}")
async def delete_file(file_id: str, user_email: str):
    # 1. Verify ownership
    file_doc = await FileMetadata.get(file_id)
    if not file_doc:
        return {"error": "File not found"}
    if file_doc.user_email != user_email:
        return {"error": "Unauthorized"}
        
    # 2. Delete from GridFS
    if file_doc.gridfs_id:
        try:
            await StorageService.delete_file(file_doc.gridfs_id)
        except Exception as e:
            print(f"Error deleting from GridFS: {e}")
    
    # 3. Delete Chunks
    await Chunk.find(Chunk.document_id == file_id).delete()
    
    # 4. Delete Meta
    await file_doc.delete()
    
    return {"message": "File and chunks deleted"}
