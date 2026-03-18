from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.config import get_settings
from app.routers import health, documents, chat

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run on startup: create tables and pgvector extension."""
    await init_db()
    yield
    # (add shutdown cleanup here if needed)


app = FastAPI(
    title="Agentic RAG API",
    version="1.0.0",
    description="Chat with your documents using an agent that decides when to retrieve.",
    lifespan=lifespan,
)

# CORS — allow the React dev server (and production origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # React dev server
        "http://localhost:5173",   # Vite dev server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(documents.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
