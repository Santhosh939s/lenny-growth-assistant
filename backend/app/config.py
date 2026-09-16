from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: Optional[str] = None

    # Model Providers
    MODEL_PROVIDER: str = "ollama"  # Default to local
    
    # Cloud Models
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-haiku-20240307"
    OPENAI_API_KEY: Optional[str] = None
    CLOUD_MODEL: Optional[str] = None
    
    # Local Models
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_CHAT_MODEL: str = "qwen3:1.7b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    TRANSCRIPT_SOURCE_DIR: Optional[str] = None
    LENNY_TRANSCRIPTS_PATH: str = "../lennys-podcast-transcripts"

    @property
    def transcripts_path(self) -> str:
        return self.TRANSCRIPT_SOURCE_DIR or self.LENNY_TRANSCRIPTS_PATH

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
