from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # MongoDB
    MONGODB_URI: str
    MONGODB_DATABASE: str = "knowledge_capture_db"
    
    # Voyage AI (Embeddings)
    VOYAGE_API_KEY: str
    VOYAGE_MODEL: str = "voyage-3-large" 
    VOYAGE_RERANK_MODEL: str = "rerank-2.5"
    VECTOR_SEARCH_WEIGHT: float = 0.5 
    
    # Gemini (LLM)
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"

    # API Auth (Simple Admin Key since Clerk is removed)
    ADMIN_API_KEY: str = "secret-admin-key" 

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings():
    return Settings()
