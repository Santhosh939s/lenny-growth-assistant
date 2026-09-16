import logging
import json
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from app.services.llm.base import LLMProvider
from app.config import settings

logger = logging.getLogger(__name__)

class AnthropicProvider(LLMProvider):
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is missing")
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.ANTHROPIC_MODEL

    @property
    def provider_name(self) -> str:
        return f"Anthropic · {self.model}"

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        # Convert OpenAI-style messages to Anthropic style
        anthropic_messages = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                # System prompts should be passed separately in Anthropic, but for simplicity
                # we'll prepend it to the first user message or ignore if not supported this way.
                continue
                
            if role == "tool":
                # Convert OpenAI tool response to Anthropic tool result
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id"),
                        "content": msg.get("content", "")
                    }]
                })
            elif "tool_calls" in msg:
                # Convert OpenAI tool call to Anthropic tool use
                content = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    fn = tc["function"]
                    content.append({
                        "type": "tool_use",
                        "id": tc.get("id", "call_123"),
                        "name": fn["name"],
                        "input": json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                    })
                anthropic_messages.append({"role": "assistant", "content": content})
            else:
                anthropic_messages.append({"role": role, "content": msg["content"]})

        # Merge consecutive messages with identical roles for Anthropic compliance
        merged_messages = []
        for msg in anthropic_messages:
            if merged_messages and merged_messages[-1]["role"] == msg["role"]:
                prev = merged_messages[-1]
                prev_content = prev["content"]
                curr_content = msg["content"]
                if isinstance(prev_content, str) and isinstance(curr_content, str):
                    prev["content"] = prev_content + "\n\n" + curr_content
                elif isinstance(prev_content, list) and isinstance(curr_content, list):
                    prev["content"] = prev_content + curr_content
                elif isinstance(prev_content, list):
                    prev["content"] = prev_content + [{"type": "text", "text": str(curr_content)}]
                else:
                    prev["content"] = [{"type": "text", "text": str(prev_content)}, {"type": "text", "text": str(curr_content)}]
            else:
                merged_messages.append(msg)
        anthropic_messages = merged_messages

        # Extract system prompt if present
        system_prompt = next((m["content"] for m in messages if m["role"] == "system"), None)

        # Convert OpenAI tools to Anthropic tools
        anthropic_tools = []
        if tools:
            for t in tools:
                if t.get("type") == "function":
                    fn = t["function"]
                    anthropic_tools.append({
                        "name": fn["name"],
                        "description": fn.get("description", ""),
                        "input_schema": fn["parameters"]
                    })

        kwargs = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": anthropic_messages
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
            
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        try:
            response = self.client.messages.create(**kwargs)
            
            # Parse response back to our agnostic format
            content = ""
            tool_calls = []
            
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "arguments": block.input  # Dict
                    })
                    
            return {
                "content": content,
                "tool_calls": tool_calls
            }
        except Exception as e:
            logger.error(f"Anthropic chat error: {e}")
            raise RuntimeError(f"Anthropic provider failed: {str(e)}")
