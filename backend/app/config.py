from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "Agentic RAG"
    environment: str = "development"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://rag_user:rag_pass@localhost:5432/rag_db"

    # OpenAI
    openai_api_key: str
    openai_chat_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536

    # Document processing
    chunk_size: int = 512          # tokens per chunk
    chunk_overlap: int = 64        # token overlap between chunks
    retriever_top_k: int = 6       # how many chunks to retrieve

    # File uploads
    upload_dir: str = "/tmp/uploads"
    max_file_size_mb: int = 50
    allowed_extensions: list[str] = ["pdf", "txt", "docx", "md"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
