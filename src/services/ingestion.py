import os
import tempfile
import voyageai
from src.services.storage import StorageService
from src.models.files import FileMetadata, Chunk
from src.config import get_settings

# Docling
try:
    from docling.document_converter import DocumentConverter
except ImportError:
    DocumentConverter = None

class IngestionService:
    @staticmethod
    async def process_document(file_id: str):
        settings = get_settings()
        file_meta = await FileMetadata.get(file_id)
        if not file_meta:
            raise Exception("Metadata not found")
        
        try:
            # 1. Download
            file_data = await StorageService.download_file(file_meta.gridfs_id)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_meta.filename}") as tmp:
                tmp.write(file_data)
                tmp_path = tmp.name
            
            # 2. Parse (Docling)
            if DocumentConverter:
                converter = DocumentConverter()
                result = converter.convert(tmp_path)
                doc = result.document
                # Simple markdown splitting for reliable chunks
                # Future: Use HybridChunker properly
                markdown_content = doc.export_to_markdown()
                chunks_text = IngestionService._chunk_text(markdown_content)
            else:
                chunks_text = ["Mock Content 1", "Mock Content 2"]

            # 3. Embed (Voyage AI)
            vo = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
            
            # Batch embedding
            if chunks_text:
                # voyage-3 returns list of embeddings
                embeddings = vo.embed(chunks_text, model=settings.VOYAGE_MODEL, input_type="document").embeddings
                
                chunk_docs = []
                for i, text in enumerate(chunks_text):
                    chunk_docs.append(Chunk(
                        document_id=str(file_meta.id),
                        project_id=file_meta.project_id,
                        chunk_index=i,
                        content=text,
                        embedding=embeddings[i],
                        metadata={"source": file_meta.filename}
                    ))
                
                await Chunk.insert_many(chunk_docs)

            file_meta.status = "completed"
            await file_meta.save()
            os.unlink(tmp_path)

        except Exception as e:
            file_meta.status = "failed"
            file_meta.error_message = str(e)
            await file_meta.save()
            raise e

    @staticmethod
    def _chunk_text(text: str, chunk_size=1000, overlap=200):
        # Naive chunker
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size-overlap)]
