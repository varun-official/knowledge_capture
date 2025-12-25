from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List

from src.services.llm import LLMService
from src.retrieval.service import SearchService
from src.config import get_settings

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatRequest(BaseModel):
    query: str
    user_email: str
    rag_strategy: str = "vector" # vector, keyword, hybrid, multi_query_vector, multi_query_hybrid, query_decompose_vector, query_decompose_hybrid

class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]

@router.post("/query", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    settings = get_settings()
    
    # 1. Retrieval
    # user_email acts as the corpus identifier
    results = await SearchService.search(
        query=request.query, 
        user_corpus=request.user_email, 
        strategy=request.rag_strategy
    )
    
    if not results:
        return ChatResponse(answer="No info found.", sources=[])
    
    # 2. Context
    context_text = "\n\n".join([f"Source: {r.content}" for r in results[:5]])
    
    # 3. Generate Answer
    from src.services.llm import LLMService

    system_prompt = ( "You are a helpful AI assistant that answers questions based solely on the provided context. "
        "Your task is to provide accurate, detailed answers using ONLY the information available in the context below.\n\n"
        "IMPORTANT RULES:\n"
        "- Only answer based on the provided context (texts, tables, and images)\n"
        "- If the answer cannot be found in the context, respond with: 'I don't have enough information in the provided context to answer that question.'\n"
        "- Do not use external knowledge or make assumptions beyond what's explicitly stated\n"
        "- When referencing information, be specific and cite relevant parts of the context\n"
        "- Synthesize information from texts, tables, and images to provide comprehensive answers\n\n")
    user_message = f"Context:\n{context_text}\n\nQuestion: {request.query}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    answer_text = await LLMService.get_response(messages)
    
    # 4. Response
    sources = [
        {
            "content": r.content[:200], 
            "score": r.similarity,
            "document_id": r.document_id,
            "metadata": r.metadata
        } 
        for r in results[:5]
    ]
    
    return ChatResponse(answer=answer_text, sources=sources)
