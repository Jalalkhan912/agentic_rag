from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.models import DocumentChunk, Document
from app.services.embeddings import embed_query
from app.config import get_settings

settings = get_settings()


async def retrieve(query: str, db: AsyncSession, top_k: int | None = None) -> list[dict]:
    """
    Semantic search over document chunks using pgvector cosine similarity.

    This function is what the agent calls as a tool — it embeds the query,
    finds the most relevant chunks, and returns them with source metadata
    so the agent can cite them in its answer.

    Returns a list of dicts with: content, score, document_name, page_number, chunk_id
    """
    k = top_k or settings.retriever_top_k

    # Embed the query using the same model used during ingestion
    query_vector = await embed_query(query)

    # pgvector cosine distance operator: <=>
    # Lower distance = more similar. We select only "ready" documents.
    sql = text("""
        SELECT
            dc.id::text        AS chunk_id,
            dc.content         AS content,
            dc.page_number     AS page_number,
            d.original_name    AS document_name,
            d.id::text         AS document_id,
            1 - (dc.embedding <=> CAST(:query_vec AS vector)) AS similarity_score
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE d.status = 'ready'
        ORDER BY dc.embedding <=> CAST(:query_vec AS vector)
        LIMIT :top_k
    """)

    result = await db.execute(
        sql,
        {
            "query_vec": str(query_vector),
            "top_k": k,
        },
    )
    rows = result.mappings().all()

    return [
        {
            "chunk_id": row["chunk_id"],
            "content": row["content"],
            "page_number": row["page_number"],
            "document_name": row["document_name"],
            "document_id": row["document_id"],
            "similarity_score": round(float(row["similarity_score"]), 4),
        }
        for row in rows
    ]


# ── OpenAI tool definition ─────────────────────────────────────────────────
# This is the schema the agent uses to decide when/how to call the retriever.

RETRIEVER_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "retrieve_documents",
        "description": (
            "Search the user's document library for information relevant to a query. "
            "Call this when the user's question is likely answered by their uploaded documents. "
            "Do NOT call this for general knowledge questions, greetings, or follow-up clarifications "
            "that are already answered by the conversation history."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A focused search query optimised for semantic similarity. "
                        "Rephrase the user's question as a declarative statement if possible. "
                        "Example: instead of 'what is the refund policy?' use 'refund policy terms and conditions'."
                    ),
                }
            },
            "required": ["query"],
        },
    },
}
