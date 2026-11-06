# Agentic RAG — Chat With Your Documents

A full-stack **agentic retrieval-augmented generation (RAG)** app. Upload PDFs, Word documents, text or Markdown files, then ask questions about them in a chat interface.

Many RAG pipelines run a vector search before every answer. This app works differently: an **LLM agent decides on each turn whether it needs to search your documents.** Greetings, follow-ups and general-knowledge questions are answered directly. Questions about your documents trigger a semantic search, and the answer cites its sources by document and page.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?logo=openai&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

---

## Features

- **Agentic retrieval.** GPT-4o function calling with a `retrieve_documents` tool. The model chooses when to search and writes its own search query.
- **Source citations.** Each answer can show the chunks it used, with document name, page number and similarity score.
- **Document ingestion pipeline.** Extracts text from PDF, DOCX, TXT and MD files, splits it into overlapping token-based chunks (tiktoken), creates embeddings in batches and stores them in **pgvector**.
- **Background processing.** Uploads return right away while ingestion runs in the background. The UI polls and shows each file's status (pending, processing, ready or failed).
- **Saved conversations.** Chat history is stored in Postgres, and the most recent messages are sent back to the model as context.
- **Works with OpenAI or Gemini's free tier.** Any OpenAI-compatible API can be used by setting a base URL. Embedding requests are batched and retried automatically when a free tier's rate limit is hit.
- **Production-style setup.** Async SQLAlchemy, Docker Compose for local development, and a GitHub Actions pipeline: test → build images → push to AWS ECR → deploy to EC2 staging → production deploy gated on manual approval.

## Architecture

```mermaid
flowchart LR
    subgraph Frontend["React + Vite (port 3000)"]
        UI[Chat & Document Library]
    end

    subgraph Backend["FastAPI (port 8000)"]
        API[REST API /api/v1]
        Agent[Agent loop]
        Ingest[Ingestion pipeline<br/>extract → chunk → embed]
        Retriever[Retriever tool]
    end

    DB[(PostgreSQL + pgvector)]
    OpenAI[[OpenAI API<br/>GPT-4o + embeddings]]

    UI -- "/api proxy" --> API
    API -- upload --> Ingest
    Ingest -- embeddings --> OpenAI
    Ingest -- chunks + vectors --> DB
    API -- chat --> Agent
    Agent <-- function calling --> OpenAI
    Agent -- "retrieve_documents(query)" --> Retriever
    Retriever -- cosine similarity --> DB
```

### How the agent answers a message

1. The backend loads the last 20 messages of the conversation and sends them to GPT-4o with a system prompt and the `retrieve_documents` tool definition.
2. **If the model can answer directly** (a greeting, a follow-up, general knowledge), it replies with no tool call and the loop ends.
3. **If it needs your documents**, it calls `retrieve_documents` with a search query it has rephrased itself. The retriever embeds that query and runs a pgvector cosine-distance search (`<=>`) over chunks from documents with status `ready`, returning the top-k matches.
4. The chunks are formatted as labelled sources (`[Source 1: report.pdf, page 4]`) and sent back to the model as tool results. The model then writes an answer that cites them.
5. The loop is capped at 3 model calls. The user message, the assistant reply and the retrieved sources are saved to the database.

### Ingestion pipeline

```
upload → validate type/size → save to disk → Document(status=pending)
       → background task:
           extract text per page (PyPDF2 / python-docx / plain text)
           → token chunks (512 tokens, 64 overlap, cl100k_base)
           → batch embeddings (text-embedding-3-small, 1536 dims)
           → DocumentChunk rows with vector + page number
           → Document(status=ready, chunk_count=N)   or   status=failed + error_message
```

## Tech Stack

| Layer | Technology |
|---|---|
| LLM & embeddings | OpenAI `gpt-4o` + `text-embedding-3-small`, or Gemini `gemini-3.6-flash` + `gemini-embedding-001` |
| Backend | FastAPI, async SQLAlchemy 2.0, asyncpg, Pydantic v2 |
| Vector store | PostgreSQL 16 + pgvector |
| Document parsing | PyPDF2, python-docx, tiktoken |
| Frontend | React 18, Vite, React Router, react-markdown, react-dropzone |
| Infrastructure | Docker, Docker Compose, GitHub Actions, AWS ECR, EC2 |
| Testing | pytest, pytest-asyncio, httpx |

## Getting Started

### Prerequisites

- Docker and Docker Compose
- An OpenAI API key, **or** a free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Run with Docker Compose

```bash
git clone https://github.com/Jalalkhan912/agentic_rag.git
cd agentic_rag

cp .env.example .env
# edit .env: set OPENAI_API_KEY, or uncomment the Gemini block (Option B)

docker compose up --build
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API | http://localhost:8000 |
| Interactive API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

On startup the backend enables the `vector` extension and creates the tables. To try it out, upload a few documents on the **Documents** page, wait until they show **Ready**, then ask questions on the **Chat** page.

### Using Gemini's free tier

The backend uses the OpenAI SDK, and Gemini provides an [OpenAI-compatible endpoint](https://ai.google.dev/gemini-api/docs/openai), so switching providers only requires settings:

```env
OPENAI_API_KEY=<your Gemini API key>
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_CHAT_MODEL=gemini-3.6-flash
OPENAI_EMBEDDING_MODEL=gemini-embedding-001
```

Embeddings are still requested at 1536 dimensions, so the database schema is the same for both providers. Notes on the free tier:
- Rate limits are low (around 100 embedded texts per minute). Large documents ingest more slowly because the app waits and retries when it hits the limit.
- Google may use free-tier content to improve its products, so use sample documents rather than private ones.
- Embeddings from different models aren't comparable. If you switch embedding models, re-upload your documents.

### Run without Docker (local development)

Start Postgres with pgvector (for example just that one service from Compose):

```bash
docker compose up -d postgres
```

Backend (Python 3.12):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # set OPENAI_API_KEY; DATABASE_URL points at localhost
uvicorn app.main:app --reload --port 8000
```

Frontend (Node 20):

```bash
cd frontend
npm install
npm run dev                    # http://localhost:3000, proxies /api to :8000
```

## Configuration

The backend reads these settings from environment variables or `.env` (see [`backend/app/config.py`](backend/app/config.py)):

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI (or Gemini) API key |
| `OPENAI_BASE_URL` | *(unset → OpenAI)* | Base URL of any OpenAI-compatible API, such as Gemini |
| `OPENAI_CHAT_MODEL` | `gpt-4o` | Model used by the agent |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `OPENAI_EMBEDDING_DIMENSIONS` | `1536` | Vector size (must match the pgvector column) |
| `EMBEDDING_BATCH_SIZE` | `100` | Texts per embedding request (Gemini allows at most 100) |
| `EMBEDDING_MAX_RETRIES` | `6` | Retries with backoff when the embedding API rate-limits |
| `DATABASE_URL` | `postgresql+asyncpg://rag_user:rag_pass@localhost:5432/rag_db` | Async Postgres URL |
| `CHUNK_SIZE` | `512` | Tokens per chunk |
| `CHUNK_OVERLAP` | `64` | Overlapping tokens between chunks |
| `RETRIEVER_TOP_K` | `6` | Chunks returned per search |
| `MAX_FILE_SIZE_MB` | `50` | Upload size limit per file |
| `UPLOAD_DIR` | `/tmp/uploads` | Where uploaded files are stored |
| `ENVIRONMENT` | `development` | Reported by `/health` |
| `DEBUG` | `true` | Enables SQL echo logging |

## API Reference

All endpoints except `/health` are prefixed with `/api/v1`. Full schemas are at `/docs`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service status, version and configured chat model |
| `POST` | `/documents/upload` | Upload one or more files (multipart field `files`), returns `202` |
| `GET` | `/documents?skip=0&limit=50` | List documents with ingestion status |
| `GET` | `/documents/{id}` | Get one document |
| `DELETE` | `/documents/{id}` | Delete a document, its file and its chunks |
| `POST` | `/chat/message` | Send a message, which runs the agent; creates a conversation if `conversation_id` is omitted |
| `GET` | `/chat/conversations` | List conversations, most recently active first |
| `POST` | `/chat/conversations` | Create an empty conversation |
| `GET` | `/chat/conversations/{id}` | Conversation with full message history |
| `DELETE` | `/chat/conversations/{id}` | Delete a conversation |

Example:

```bash
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "What does the contract say about termination?"}'
```

```json
{
  "conversation_id": "6f1c…",
  "message": { "role": "assistant", "content": "According to contract.pdf (page 7)…", "...": "..." },
  "sources": [
    { "document_name": "contract.pdf", "page_number": 7, "similarity_score": 0.83, "content": "…" }
  ]
}
```

## Project Structure

```
agentic_rag/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, lifespan (DB init)
│   │   ├── config.py                # Pydantic settings
│   │   ├── database.py              # Async engine, session, pgvector setup
│   │   ├── models.py                # Document, DocumentChunk, Conversation, Message
│   │   ├── schemas.py               # Request/response models
│   │   ├── routers/                 # health, documents, chat endpoints
│   │   └── services/
│   │       ├── agent.py             # Agent loop with OpenAI function calling
│   │       ├── retriever.py         # pgvector search + tool definition
│   │       ├── document_processor.py# Extract → chunk → embed → store
│   │       └── embeddings.py        # Batched embeddings with rate-limit retries
│   ├── tests/                       # Smoke, agent, chunking and embedding tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/client.js            # Axios API client
│   │   ├── hooks/                   # Conversations context, document polling
│   │   ├── components/layout/       # Sidebar + shell
│   │   └── pages/                   # ChatPage, DocumentsPage
│   ├── Dockerfile
│   └── vite.config.js
├── .github/workflows/cicd.yml       # Test → build → ECR → staging → production
├── docker-compose.yml
└── .env.example
```

## Testing

The tests need no database or OpenAI access. The OpenAI client and the retriever are mocked.

```bash
cd backend
OPENAI_API_KEY=sk-test pytest -v
```

The suite covers:
- **Smoke tests:** the app starts, `/health` responds, and unsupported file types are rejected.
- **Agent loop:** direct answers, every tool call getting a reply, malformed tool arguments, and de-duplication of sources.
- **Document processing:** chunk size and overlap, empty input, and removal of NUL bytes.
- **Embeddings:** batching, and retrying when rate-limited.

## CI/CD

[`.github/workflows/cicd.yml`](.github/workflows/cicd.yml) runs on every push and pull request to `main`:

1. **Lint & Test:** installs dependencies and runs pytest against a pgvector service container.
2. **Build & Push** (main only): builds the backend and frontend images and pushes them to **AWS ECR**, tagged with the commit SHA and `latest`.
3. **Deploy → Staging:** connects to an EC2 host over SSH, pulls the images and restarts the containers on a shared Docker network, then runs a health check.
4. **Deploy → Production:** the same steps on the production host, gated by a GitHub **environment approval**.

Required repository secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `ECR_REGISTRY`, `OPENAI_API_KEY`, `DB_PASSWORD`, `EC2_HOST`, `EC2_USERNAME`, `EC2_SSH_KEY`.

## Design Decisions

- **The agent decides when to retrieve.** Skipping retrieval for small talk and follow-ups saves embedding calls and keeps unrelated chunks out of the prompt.
- **pgvector instead of a separate vector database.** Documents, chunks, conversations and embeddings live in one Postgres instance, which keeps transactions consistent and leaves one fewer service to run.
- **Token-based chunking with overlap.** Chunks line up with the model's tokenizer, and the overlap keeps sentences that cross a chunk boundary searchable.
- **Page-level metadata.** Each chunk keeps its page number, so citations point to a specific page.

## Possible Improvements

- Stream responses to the UI (server-sent events)
- Hybrid search (BM25 + vectors) and re-ranking
- An HNSW index on `document_chunks.embedding` for large libraries
- Database migrations with Alembic instead of `create_all`
- Authentication and per-user document libraries
- A durable job queue (such as Celery or Arq) instead of in-process background tasks
- Serving the frontend as a static production build (Nginx) instead of the Vite dev server
