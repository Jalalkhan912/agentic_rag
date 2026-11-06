from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "Agentic RAG"
    environment: str = "development"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://rag_user:rag_pass@localhost:5432/rag_db"

    # OpenAI (or any OpenAI-compatible API, e.g. Gemini — set openai_base_url)
    openai_api_key: str
    openai_base_url: str | None = None
    openai_chat_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    embedding_batch_size: int = 100   # Gemini allows at most 100 inputs per request
    embedding_max_retries: int = 6    # retries on rate-limit (429) errors

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
