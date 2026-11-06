import uuid
import asyncio
from pathlib import Path
import tiktoken

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models import Document, DocumentChunk, DocumentStatus
from app.services.embeddings import embed_texts
from app.config import get_settings

settings = get_settings()

# Tokenizer — must match the embedding model family
_tokenizer = tiktoken.get_encoding("cl100k_base")


# ── Text extraction ────────────────────────────────────────────────────────

def extract_text_from_pdf(file_path: Path) -> list[tuple[str, int]]:
    """Returns list of (page_text, page_number) tuples."""
    import PyPDF2
    pages = []
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.replace("\x00", "").strip():
                pages.append((text, i))
    return pages


def extract_text_from_docx(file_path: Path) -> list[tuple[str, int]]:
    """Returns the full text as a single 'page'."""
    from docx import Document as DocxDocument
    doc = DocxDocument(str(file_path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [(text, 1)]


def extract_text_from_txt(file_path: Path) -> list[tuple[str, int]]:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    return [(text, 1)]


def extract_text(file_path: Path, file_type: str) -> list[tuple[str, int]]:
    extractors = {
        "pdf": extract_text_from_pdf,
        "docx": extract_text_from_docx,
        "txt": extract_text_from_txt,
        "md": extract_text_from_txt,
    }
    extractor = extractors.get(file_type.lower())
    if not extractor:
        raise ValueError(f"Unsupported file type: {file_type}")
    # Postgres TEXT columns reject NUL bytes, which some PDFs contain
    return [(text.replace("\x00", ""), page) for text, page in extractor(file_path)]


# ── Chunking ───────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = settings.chunk_size,
    overlap: int = settings.chunk_overlap,
) -> list[tuple[str, int]]:
    """
    Split text into overlapping token chunks.
    Returns list of (chunk_text, token_count).
    """
    tokens = _tokenizer.encode(text)
    chunks = []
    start = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = _tokenizer.decode(chunk_tokens)
        chunks.append((chunk_text, len(chunk_tokens)))
        if end == len(tokens):
            break
        start += chunk_size - overlap

    return chunks


# ── Main ingestion pipeline ────────────────────────────────────────────────

async def process_document(document_id: uuid.UUID, file_path: Path, db: AsyncSession):
    """
    Full ingestion pipeline:
      1. Extract text from file
      2. Chunk by tokens with overlap
      3. Batch-embed all chunks via OpenAI
      4. Persist DocumentChunk rows with embeddings
      5. Update document status
    """
    try:
        # Mark as processing
        await db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status=DocumentStatus.processing)
        )
        await db.commit()

        # Fetch the document row to get file_type
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one()

        # 1. Extract text (list of (text, page_number))
        # Parsing is CPU-bound, so keep it off the event loop
        pages = await asyncio.to_thread(extract_text, file_path, document.file_type)
        if not pages:
            raise ValueError("No extractable text found in document.")

        # 2. Chunk each page and track page numbers
        all_chunks: list[dict] = []
        for page_text, page_num in pages:
            for chunk_text_val, token_count in chunk_text(page_text):
                all_chunks.append({
                    "content": chunk_text_val,
                    "token_count": token_count,
                    "page_number": page_num,
                })

        if not all_chunks:
            raise ValueError("Text extraction produced no chunks.")

        # 3. Embed all chunks in one batched call
        texts_to_embed = [c["content"] for c in all_chunks]
        embeddings = await embed_texts(texts_to_embed)

        # 4. Persist chunks
        chunk_objects = []
        for idx, (chunk_data, embedding) in enumerate(zip(all_chunks, embeddings)):
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=idx,
                content=chunk_data["content"],
                token_count=chunk_data["token_count"],
                page_number=chunk_data["page_number"],
                embedding=embedding,
            )
            chunk_objects.append(chunk)

        db.add_all(chunk_objects)

        # 5. Mark document as ready
        await db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status=DocumentStatus.ready, chunk_count=len(chunk_objects))
        )
        await db.commit()

    except Exception as exc:
        await db.rollback()
        await db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status=DocumentStatus.failed, error_message=str(exc))
        )
        await db.commit()
        raise
