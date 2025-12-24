from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from beanie import init_beanie
from src.config import get_settings
from src.models.core import User, Project
from src.models.files import FileMetadata, Chunk
from src.models.task import Task

class Database:
    client: AsyncIOMotorClient = None
    fs: AsyncIOMotorGridFSBucket = None

    async def connect(self):
        settings = get_settings()
        self.client = AsyncIOMotorClient(settings.MONGODB_URI)
        db = self.client[settings.MONGODB_DATABASE]
        
        self.fs = AsyncIOMotorGridFSBucket(db)
        
        await init_beanie(database=db, document_models=[User, Project, FileMetadata, Chunk, Task])
        print(f"Connected to MongoDB: {settings.MONGODB_DATABASE}")

    async def close(self):
        if self.client:
            self.client.close()

db = Database()
