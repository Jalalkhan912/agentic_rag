import logging
import uuid
import aiofiles
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Document
from app.schemas import DocumentOut, DocumentListOut
from app.services.document_processor import process_document
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = set(settings.allowed_extensions)
MAX_BYTES = settings.max_file_size_mb * 1024 * 1024


@router.post("/upload", response_model=list[DocumentOut], status_code=202)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload one or many files. Each file is saved to disk, a Document row is
    created with status=pending, and processing is queued as a background task.
    Returns immediately — poll /documents/{id} for status updates.
    """
    # Validate every file first so a bad file doesn't leave the others half-uploaded
    validated: list[tuple[UploadFile, str, bytes]] = []
    for file in files:
        name = file.filename or "unnamed"
        suffix = Path(name).suffix.lstrip(".").lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"'{name}': unsupported type '{suffix}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
            )

        content = await file.read()
        if len(content) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"'{name}' exceeds {settings.max_file_size_mb} MB limit.",
            )
        validated.append((file, suffix, content))

    created_docs = []
    for file, suffix, content in validated:
        # Save to disk with a UUID-based name to avoid collisions
        file_id = uuid.uuid4()
        stored_name = f"{file_id}.{suffix}"
        file_path = UPLOAD_DIR / stored_name

        async with aiofiles.open(file_path, "wb") as out:
            await out.write(content)

        document = Document(
            id=file_id,
            filename=stored_name,
            original_name=(file.filename or stored_name)[:255],
            file_type=suffix,
            file_size_bytes=len(content),
        )
        db.add(document)
        created_docs.append(document)

    await db.commit()
    for document in created_docs:
        await db.refresh(document)
        # Queue background ingestion
        background_tasks.add_task(
            _run_processing,
            document_id=document.id,
            file_path=UPLOAD_DIR / document.filename,
        )

    return created_docs


@router.get("", response_model=DocumentListOut)
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count()).select_from(Document))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit)
    )
    docs = result.scalars().all()
    return DocumentListOut(documents=list(docs), total=total)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Delete file from disk
    file_path = UPLOAD_DIR / doc.filename
    if file_path.exists():
        file_path.unlink()

    # Cascade deletes chunks automatically (ondelete="CASCADE")
    await db.delete(doc)
    await db.commit()


# ── Background processing helper ───────────────────────────────────────────

async def _run_processing(document_id: uuid.UUID, file_path: Path):
    """Runs in background. Creates its own DB session."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await process_document(document_id, file_path, db)
        except Exception:
            # Failure is already recorded on the document row (status=failed)
            logger.exception("Ingestion failed for document %s", document_id)
