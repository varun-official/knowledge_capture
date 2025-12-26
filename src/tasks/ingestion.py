from beanie_batteries_queue import Task

class IngestionTask(Task):
    file_id: str

    async def run(self):
        from src.ingestion.service import IngestionService
        print(f"Processing Ingestion Task for File: {self.file_id}")
        await IngestionService.process_document(self.file_id)
