from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class LLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the provider and model."""
        pass

    @abstractmethod
    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Send a chat request.
        
        Args:
            messages: List of message dictionaries, e.g., [{"role": "user", "content": "hello"}]
            tools: Optional list of tools defined in OpenAI format.
            
        Returns:
            Dict containing:
                - "content": Text content of the response (if any)
                - "tool_calls": List of tool calls [{"name": "tool_name", "arguments": {...}}] (if any)
        """
        pass
