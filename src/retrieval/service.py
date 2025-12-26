from src.db.mongo import db
from src.config import get_settings
from typing import List, Dict, Any
from pydantic import BaseModel
import voyageai
import asyncio
from src.services.llm import LLMService

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
    async def vector_search(query_embedding: List[float], user_corpus: str, limit: int = 20) -> List[SearchResult]:
        search_stage = {
            "index": "vector_index",
            "path": "embedding",
            "queryVector": query_embedding,
            "numCandidates": 100,
            "limit": limit
        }
        
        # Add filter if user_corpus provided
        if user_corpus:
             search_stage["filter"] = {"user_corpus": {"$eq": user_corpus}}

        pipeline = [
            {"$vectorSearch": search_stage},
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
    async def keyword_search(query: str, user_corpus: str, limit: int = 20) -> List[SearchResult]:
        search_operator = {
            "text": {"query": query, "path": "content"}
        }
        
        if user_corpus:
            search_operator = {
                "compound": {
                    "must": [{"text": {"query": query, "path": "content"}}],
                    "filter": [{"text": {"query": user_corpus, "path": "user_corpus"}}]
                }
            }

        pipeline = [
            {
                "$search": {
                    "index": "text_index",
                    **search_operator
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
    def rerank_results(query: str, results: List[SearchResult], top_k: int = 20) -> List[SearchResult]:
        if not results:
            return []
            
        settings = get_settings()
        vo = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
        
        # Extract content for reranking
        documents = [r.content for r in results]
        
        try:
            reranking = vo.rerank(query, documents, model=settings.VOYAGE_RERANK_MODEL, top_k=top_k)
            
            reranked_results = []
            for r in reranking.results:
                # Map back to original result using index
                original_result = results[r.index]
                # Update similarity score with reranking score
                original_result.similarity = r.relevance_score
                reranked_results.append(original_result)
                
            return reranked_results
        except Exception as e:
            print(f"ERROR: Reranking failed: {e}")
            # Fallback to original order/scores if reranking fails
            return results[:top_k]

    @staticmethod
    async def hybrid_search(query: str, user_corpus: str = None, limit: int = 20) -> List[SearchResult]:
        print(f"DEBUG: Starting Hybrid Search for query: '{query}' in corpus: '{user_corpus}'")
        
        # Sync embedding call (Voyage is sync client) wrapped if needed
        query_vec = await asyncio.to_thread(SearchService.get_embedding, query)
        print(f"DEBUG: Generated Embedding. Size: {len(query_vec)}")
        
        # Parallel search
        vec_res, kw_res = await asyncio.gather(
            SearchService.vector_search(query_vec, user_corpus),
            SearchService.keyword_search(query, user_corpus)
        )
        
        print(f"DEBUG: Vector Search Results: {len(vec_res)}")
        print(f"DEBUG: Keyword Search Results: {len(kw_res)}")
        
        if vec_res:
            print(f"DEBUG: Top Vector Match: {vec_res[0].content[:50]}... (Score: {vec_res[0].similarity})")
        if kw_res:
             print(f"DEBUG: Top Keyword Match: {kw_res[0].content[:50]}... (Score: {kw_res[0].similarity})")

        # Fuse
        final_results = SearchService.rrf_fusion([vec_res, kw_res])[:limit]
        print(f"DEBUG: Final Fused Results: {len(final_results)}")
        
        return final_results

    @staticmethod
    async def generate_query_variations(query: str, n: int = 2) -> List[str]:
        prompt = f"Generate {n} alternative ways to phrase this question for document search. Use different keywords and synonyms while maintaining the same intent. Return exactly {n} variations, one per line."
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Query: {query}"}
        ]
        
        response = await LLMService.get_response(messages)
        variations = [line.strip() for line in response.split("\n") if line.strip()]
        
        # Ensure we have at least the original query
        return [query] + variations[:n]

    @staticmethod
    async def multi_query_vector_search(query: str, user_corpus: str, limit: int = 20) -> List[SearchResult]:
        print(f"DEBUG: Generating variations for vector search: '{query}'")
        queries = await SearchService.generate_query_variations(query)
        print(f"DEBUG: Generated variations: {queries}")
        
        # Parallel search
        tasks = [SearchService.vector_search(
            await asyncio.to_thread(SearchService.get_embedding, q), 
            user_corpus
        ) for q in queries]
        
        results_lists = await asyncio.gather(*tasks)
        return SearchService.rrf_fusion(results_lists)[:limit]

    @staticmethod
    async def multi_query_hybrid_search(query: str, user_corpus: str, limit: int = 20) -> List[SearchResult]:
        print(f"DEBUG: Generating variations for hybrid search: '{query}'")
        queries = await SearchService.generate_query_variations(query)
        
        # Parallel search
        tasks = [SearchService.hybrid_search(q, user_corpus) for q in queries]
        
        results_lists = await asyncio.gather(*tasks)
        return SearchService.rrf_fusion(results_lists)[:limit]

    @staticmethod
    async def decompose_query(query: str) -> List[str]:
        prompt = "Analyze this query. If it consists of multiple distinct sub-questions, extract them (max 3). If it is a single valid question, return it as is. Return distinct queries, one per line."
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Query: {query}"}
        ]
        
        response = await LLMService.get_response(messages)
        sub_queries = [line.strip() for line in response.split("\n") if line.strip()]
        
        # Fallback if empty
        if not sub_queries:
            sub_queries = [query]
            
        print(f"DEBUG: Decomposition result: {sub_queries}")
        return sub_queries

    @staticmethod
    async def query_decompose_vector_search(query: str, user_corpus: str, limit: int = 20) -> List[SearchResult]:
        print(f"DEBUG: Decomposing query for vector search: '{query}'")
        sub_queries = await SearchService.decompose_query(query)
        
        # Parallel search
        tasks = [SearchService.vector_search(
            await asyncio.to_thread(SearchService.get_embedding, q), 
            user_corpus
        ) for q in sub_queries]
        
        results_lists = await asyncio.gather(*tasks)
        return SearchService.rrf_fusion(results_lists)[:limit]

    @staticmethod
    async def query_decompose_hybrid_search(query: str, user_corpus: str, limit: int = 20) -> List[SearchResult]:
        print(f"DEBUG: Decomposing query for hybrid search: '{query}'")
        sub_queries = await SearchService.decompose_query(query)
        
        # Parallel search
        tasks = [SearchService.hybrid_search(q, user_corpus) for q in sub_queries]
        
        results_lists = await asyncio.gather(*tasks)
        return SearchService.rrf_fusion(results_lists)[:limit]

    @staticmethod
    async def search(query: str, user_corpus: str, strategy: str = "vector") -> List[SearchResult]:
        # Fetch more candidates for reranking
        initial_limit = 50
        final_limit = 20
        
        print(f"DEBUG: Search Strategy: {strategy}, Initial Limit: {initial_limit}")

        results = []
        if strategy == "query_decompose_hybrid":
             results = await SearchService.query_decompose_hybrid_search(query, user_corpus, limit=initial_limit)
        elif strategy == "query_decompose_vector":
             results = await SearchService.query_decompose_vector_search(query, user_corpus, limit=initial_limit)
        elif strategy == "multi_query_hybrid":
             results = await SearchService.multi_query_hybrid_search(query, user_corpus, limit=initial_limit)
        elif strategy == "multi_query_vector":
             results = await SearchService.multi_query_vector_search(query, user_corpus, limit=initial_limit)
        elif strategy == "hybrid":
            results = await SearchService.hybrid_search(query, user_corpus, limit=initial_limit)
        elif strategy == "keyword":
            results = await SearchService.keyword_search(query, user_corpus, limit=initial_limit)
        else:
            # Default to vector
            query_vec = await asyncio.to_thread(SearchService.get_embedding, query)
            results = await SearchService.vector_search(query_vec, user_corpus, limit=initial_limit)
            
        # Rerank
        print(f"DEBUG: Reranking {len(results)} results")
        reranked = await asyncio.to_thread(SearchService.rerank_results, query, results, final_limit)
        return reranked
