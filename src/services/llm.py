from litellm import acompletion
from src.config import get_settings

from typing import List, Dict, Optional

class LLMService:
    @staticmethod
    async def get_response(messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
        settings = get_settings()
        
        # Ensure correct prefix for LiteLLM
        if not model:
            model = settings.GEMINI_MODEL
            
        if "gemini" in model.lower() and not model.startswith("gemini/"):
            model = f"gemini/{model}"

        try:
            response = await acompletion(
                model=model,
                messages=messages,
                api_key=settings.GEMINI_API_KEY
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating answer: {str(e)}"
