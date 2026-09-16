import httpx
import json
from typing import List, Dict, Any, Optional
from app.services.llm.base import LLMProvider
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class OllamaProvider(LLMProvider):
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_CHAT_MODEL

    @property
    def provider_name(self) -> str:
        return f"Ollama · {self.model}"

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": 800,
                "temperature": 0.3,
            }
        }
        
        # Ollama natively supports tools in the /api/chat endpoint
        if tools:
            payload["tools"] = tools
            
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                
                message = data.get("message", {})
                content = message.get("content", "")
                
                tool_calls = []
                if "tool_calls" in message:
                    for tc in message["tool_calls"]:
                        fn = tc.get("function", {})
                        tool_calls.append({
                            "name": fn.get("name"),
                            "arguments": fn.get("arguments", {})
                        })
                        
                return {
                    "content": content,
                    "tool_calls": tool_calls
                }
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise RuntimeError(f"Ollama provider failed: {str(e)}")
