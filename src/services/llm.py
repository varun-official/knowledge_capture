from litellm import acompletion
from src.config import get_settings

class LLMService:
    @staticmethod
    async def generate_response(prompt: str, context: str) -> str:
        settings = get_settings()
        
        # Ensure correct prefix for LiteLLM
        model = settings.GEMINI_MODEL
        if "gemini" in model.lower() and not model.startswith("gemini/"):
            model = f"gemini/{model}"

        messages = [
            {"role": "system", "content": "You are a helpful assistant. Use the context provided to answer the user's question. If the answer is not in the context, say so."},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {prompt}"}
        ]

        try:
            response = await acompletion(
                model=model,
                messages=messages,
                api_key=settings.GEMINI_API_KEY
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating answer: {str(e)}"
