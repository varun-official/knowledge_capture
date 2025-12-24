from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List
import google.generativeai as genai
from src.services.search import SearchService
from src.config import get_settings

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatRequest(BaseModel):
    query: str
    project_id: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]

@router.post("/query", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    settings = get_settings()
    
    # 1. Retrieval
    results = await SearchService.hybrid_search(request.query)
    
    if not results:
        return ChatResponse(answer="No info found.", sources=[])
    
    # 2. Context
    context_text = "\n\n".join([f"Source: {r.content}" for r in results[:5]])
    
    # 3. Gemini Generation
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    
    prompt = f"""You are a helpful assistant. Use the context below to answer the question.
    
    Context:
    {context_text}
    
    Question: {request.query}
    """
    
    # Run in thread
    import asyncio
    response = await asyncio.to_thread(model.generate_content, prompt)
    
    # 4. Response
    sources = [{"content": r.content[:100], "score": r.similarity} for r in results[:5]]
    
    return ChatResponse(answer=response.text, sources=sources)
