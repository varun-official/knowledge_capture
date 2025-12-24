import asyncio
import logging
from src.db.mongo import db
from src.services.queue import QueueService
from src.services.ingestion import IngestionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")

async def run():
    await db.connect()
    logger.info("Worker started.")
    
    while True:
        try:
            task = await QueueService.claim_task("worker-1")
            
            if task:
                logger.info(f"Task {task.id}: {task.type}")
                if task.type == "ingestion":
                    file_id = task.payload.get("file_id")
                    if file_id:
                        await IngestionService.process_document(file_id)
                        await QueueService.complete_task(task.id, "completed")
                    else:
                        await QueueService.complete_task(task.id, "failed", "Missing file_id")
                else:
                     logger.warning("Unknown task type")
                     await QueueService.complete_task(task.id, "failed", "Unknown type")
            else:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run())
