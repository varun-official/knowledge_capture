import asyncio
import logging
from src.db.mongo import db
from src.services.queue import QueueService
from src.services.ingestion import IngestionService

logging.basicConfig(level=logging.INFO)
# Suppress noisy docling logs
logging.getLogger("docling").setLevel(logging.WARNING)

logger = logging.getLogger("worker")

import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_check():
    # Logic: Use PORT if set (Production/Render), else WORKER_PORT (Local), else 10000.
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    logger.info(f"Health check server listening on port {port}")

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
    # Start the dummy server immediately to satisfy Render's port binding requirement
    start_health_check()
    asyncio.run(run())
