from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Any
from app.models import DocumentStatus, MessageRole


# ── Documents ──────────────────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: UUID
    filename: str
    original_name: str
    file_type: str
    file_size_bytes: int
    status: DocumentStatus
    error_message: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListOut(BaseModel):
    documents: list[DocumentOut]
    total: int


# ── Conversations ──────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    title: str = "New conversation"


class ConversationOut(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationListOut(BaseModel):
    conversations: list[ConversationOut]


# ── Messages ───────────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    retrieved_chunks: list[dict] | None = None
    tool_calls: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: UUID | None = None   # None → create new conversation


class ChatResponse(BaseModel):
    conversation_id: UUID
    message: MessageOut
    # Surfaces which documents were cited so the UI can show sources
    sources: list[dict[str, Any]] = []


class ConversationHistoryOut(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]


# ── Health ─────────────────────────────────────────────────────────────────

class HealthOut(BaseModel):
    status: str
    version: str
    environment: str
    chat_model: str
