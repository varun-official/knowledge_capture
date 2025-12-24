import logging
from typing import List, Any, Optional
from dataclasses import dataclass

try:
    from docling.chunking import HybridChunker
    from docling_core.types.doc import DoclingDocument
    from transformers import AutoTokenizer
except ImportError:
    HybridChunker = None
    DoclingDocument = None
    AutoTokenizer = None

logger = logging.getLogger(__name__)

@dataclass
class ChunkResult:
    text: str
    metadata: dict

class DocumentChunker:
    def __init__(self, chunk_size=1000, chunk_overlap=200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunker = None
        self.tokenizer = None
        
        if HybridChunker and AutoTokenizer:
            try:
                # Initialize tokenizer for better precision
                model_id = "sentence-transformers/all-MiniLM-L6-v2"
                self.tokenizer = AutoTokenizer.from_pretrained(model_id)
                self.chunker = HybridChunker(
                    tokenizer=self.tokenizer,
                    merge_peers=True
                )
                logger.info("HybridChunker initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to init HybridChunker: {e}")

    def chunk(self, doc: Any) -> List[ChunkResult]:
        """
        Chunk a DoclingDocument using HybridChunker if available,
        otherwise fall back to simple text splitting.
        """
        # 1. Try Hybrid Contextual Chunking
        if self.chunker and isinstance(doc, DoclingDocument):
            try:
                chunk_iter = self.chunker.chunk(dl_doc=doc)
                results = []
                for chunk in chunk_iter:
                    # The Magic: Contextualize prepends hierarchy (e.g. "Header 1 > Subheader > content")
                    text = self.chunker.contextualize(chunk=chunk)
                    results.append(ChunkResult(text=text, metadata={"method": "hybrid"}))
                return results
            except Exception as e:
                logger.error(f"Hybrid chunking failed: {e}. Falling back.")

        # 2. Fallback: Simple Markdown Splitting
        if hasattr(doc, "export_to_markdown"):
             text = doc.export_to_markdown()
        else:
             text = str(doc)
             
        return self._simple_chunk(text)

    def _simple_chunk(self, text: str) -> List[ChunkResult]:
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk_text = text[i:i + self.chunk_size]
            chunks.append(ChunkResult(text=chunk_text, metadata={"method": "simple"}))
        return chunks
