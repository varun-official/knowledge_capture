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
    rag_strategy: str = "vector" # vector, keyword, hybrid

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
    answer_text = await LLMService.generate_response(request.query, context_text)
    
    # 4. Response
    sources = [{"content": r.content[:100], "score": r.similarity} for r in results[:5]]
    
    return ChatResponse(answer=answer_text, sources=sources)
