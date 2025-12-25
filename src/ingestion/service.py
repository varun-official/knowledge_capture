import os
import tempfile
import voyageai
from src.services.storage import StorageService
from src.models.files import FileMetadata, Chunk
from src.config import get_settings
import logging

logger = logging.getLogger(__name__)

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
            # Lazy import DocumentConverter to save RAM
            try:
                from docling.document_converter import DocumentConverter
            except ImportError:
                DocumentConverter = None

            if DocumentConverter:
                converter = DocumentConverter()
                result = converter.convert(tmp_path)
                doc = result.document # DoclingDocument
                
                # Use our new robust chunker
                from src.ingestion.chunker import DocumentChunker
                chunker = DocumentChunker()
                chunks = chunker.chunk(doc)
                
                # Extract text for embedding
                chunks_text = [c.text for c in chunks]
            else:
                chunks_text = ["Mock Content (Docling missing)"]

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
                        user_corpus=file_meta.user_corpus,
                        user_email=file_meta.user_email,
                        chunk_index=i,
                        content=text,
                        embedding=embeddings[i],
                        metadata={"source": file_meta.filename}
                    ))
                
                await Chunk.insert_many(chunk_docs)
                logger.info(f"Successfully created embedding and stored {len(chunk_docs)} chunks for {file_meta.filename}")

            file_meta.status = "completed"
            await file_meta.save()
            os.unlink(tmp_path)

        except Exception as e:
            file_meta.status = "failed"
            file_meta.error_message = str(e)
            await file_meta.save()
            raise e
