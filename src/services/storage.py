from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from fastapi import UploadFile
from src.db.mongo import db
from bson import ObjectId

class StorageService:
    @staticmethod
    async def upload_file(file: UploadFile, metadata: dict = None) -> ObjectId:
        if not db.fs:
            raise Exception("DB not connected")
        
        grid_in = db.fs.open_upload_stream(file.filename, metadata=metadata)
        
        while True:
            chunk = await file.read(1024 * 1024) # 1MB chunks
            if not chunk:
                break
            await grid_in.write(chunk)
            
        await grid_in.close()
        return grid_in._id

    @staticmethod
    async def upload_bytes(filename: str, content: bytes, metadata: dict = None) -> ObjectId:
        if not db.fs:
            raise Exception("DB not connected")
        
        grid_in = db.fs.open_upload_stream(filename, metadata=metadata)
        await grid_in.write(content)
        await grid_in.close()
        return grid_in._id

    @staticmethod
    async def download_file(file_id: str) -> bytes:
        if not db.fs:
            raise Exception("DB not connected")
        
        try:
            grid_out = await db.fs.open_download_stream(ObjectId(file_id))
            return await grid_out.read()
        except Exception as e:
            raise Exception(f"File download failed: {e}")
