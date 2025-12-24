from src.db.mongo import db
from src.config import get_settings
from typing import List, Dict, Any
from pydantic import BaseModel
import voyageai
import asyncio

class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    similarity: float
    metadata: Dict[str, Any]

class SearchService:
    @staticmethod
    def get_embedding(text: str) -> List[float]:
        settings = get_settings()
        vo = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
        return vo.embed([text], model=settings.VOYAGE_MODEL, input_type="query").embeddings[0]

    @staticmethod
    async def vector_search(query_embedding: List[float], limit: int = 20) -> List[SearchResult]:
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": 100,
                    "limit": limit
                }
            },
            {
                "$project": {"_id": 1, "document_id": 1, "content": 1, "metadata": 1, "score": {"$meta": "vectorSearchScore"}}
            }
        ]
        
        # Access motor collection directly
        chunks = db.client[get_settings().MONGODB_DATABASE]["chunks"]
        cursor = chunks.aggregate(pipeline)
        
        results = []
        async for doc in cursor:
            results.append(SearchResult(
                chunk_id=str(doc["_id"]),
                document_id=doc["document_id"],
                content=doc["content"],
                similarity=doc["score"],
                metadata=doc.get("metadata", {})
            ))
        return results

    @staticmethod
    async def keyword_search(query: str, limit: int = 20) -> List[SearchResult]:
        pipeline = [
            {
                "$search": {
                    "index": "text_index",
                    "text": {"query": query, "path": "content"}
                }
            },
            {"$limit": limit},
            {
                "$project": {"_id": 1, "document_id": 1, "content": 1, "metadata": 1, "score": {"$meta": "searchScore"}}
            }
        ]
        
        chunks = db.client[get_settings().MONGODB_DATABASE]["chunks"]
        cursor = chunks.aggregate(pipeline)
        
        results = []
        async for doc in cursor:
            results.append(SearchResult(
                chunk_id=str(doc["_id"]),
                document_id=doc["document_id"],
                content=doc["content"],
                similarity=doc["score"],
                metadata=doc.get("metadata", {})
            ))
        return results

    @staticmethod
    def rrf_fusion(results_lists: List[List[SearchResult]], k: int = 60) -> List[SearchResult]:
        rrf_map = {}
        for results in results_lists:
            for rank, result in enumerate(results):
                if result.chunk_id not in rrf_map:
                    result.similarity = 0
                    rrf_map[result.chunk_id] = result
                rrf_map[result.chunk_id].similarity += 1 / (k + rank)
        
        return sorted(rrf_map.values(), key=lambda x: x.similarity, reverse=True)

    @staticmethod
    async def hybrid_search(query: str) -> List[SearchResult]:
        print(f"DEBUG: Starting Hybrid Search for query: '{query}'")
        
        # Sync embedding call (Voyage is sync client) wrapped if needed
        query_vec = await asyncio.to_thread(SearchService.get_embedding, query)
        print(f"DEBUG: Generated Embedding. Size: {len(query_vec)}")
        
        # Parallel search
        vec_res, kw_res = await asyncio.gather(
            SearchService.vector_search(query_vec),
            SearchService.keyword_search(query)
        )
        
        print(f"DEBUG: Vector Search Results: {len(vec_res)}")
        print(f"DEBUG: Keyword Search Results: {len(kw_res)}")
        
        if vec_res:
            print(f"DEBUG: Top Vector Match: {vec_res[0].content[:50]}... (Score: {vec_res[0].similarity})")
        if kw_res:
             print(f"DEBUG: Top Keyword Match: {kw_res[0].content[:50]}... (Score: {kw_res[0].similarity})")

        # Fuse
        final_results = SearchService.rrf_fusion([vec_res, kw_res])[:20]
        print(f"DEBUG: Final Fused Results: {len(final_results)}")
        
        return final_results
