from src.models.task import Task
from datetime import datetime
from typing import Optional, Any

class QueueService:
    @staticmethod
    async def push_task(task_type: str, payload: dict) -> Task:
        task = Task(type=task_type, payload=payload, status="pending")
        await task.insert()
        return task

    @staticmethod
    async def claim_task(worker_id: str) -> Optional[Task]:
        from src.db.mongo import db
        from src.config import get_settings
        from pymongo import ReturnDocument

        # Access collection directly to avoid Beanie version conflicts
        # and ensure atomic find_one_and_update with sort works
        settings = get_settings()
        collection = db.client[settings.MONGODB_DATABASE]["tasks"]
        
        task_doc = await collection.find_one_and_update(
            {"status": "pending"},
            {"$set": {
                "status": "processing", 
                "worker_id": worker_id, 
                "started_at": datetime.now()
            }},
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER
        )
        
        if task_doc:
            return Task(**task_doc)
        return None

    @staticmethod
    async def complete_task(task_id: Any, status: str = "completed", error: str = None):
        update = {"status": status, "completed_at": datetime.now()}
        if error:
            update["error_message"] = error
        
        await Task.find_one(Task.id == task_id).update({"$set": update})
