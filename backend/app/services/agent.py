import json
from sqlalchemy.ext.asyncio import AsyncSession
from openai.types.chat import ChatCompletionMessageParam

from app.services.embeddings import get_openai_client
from app.services.retriever import retrieve, RETRIEVER_TOOL_DEFINITION
from app.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """You are a helpful assistant with access to the user's document library.

When answering questions:
- Use the retrieve_documents tool when the question is likely answered by the user's documents.
- Answer from conversation history when the question is a follow-up or clarification.
- Answer from your general knowledge only when the topic is clearly not document-specific.
- Always cite your sources by mentioning the document name when you use retrieved content.
- Be concise and direct. If the retrieved content doesn't answer the question, say so clearly.
"""


async def run_agent(
    user_message: str,
    conversation_history: list[dict],
    db: AsyncSession,
) -> dict:
    """
    Agentic RAG loop using OpenAI function calling.

    Flow:
      1. Send conversation history + new user message to GPT-4o with the retriever tool
      2. If the model calls retrieve_documents → run the retriever, inject results as a tool result
      3. Send back to the model for final answer
      4. Return the assistant's final message + any retrieved sources

    The agent may call the tool zero or more times per turn.
    We cap at 3 model calls to prevent infinite loops.
    """
    client = get_openai_client()

    # Build the full message list for this turn
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *conversation_history,
        {"role": "user", "content": user_message},
    ]

    retrieved_sources: list[dict] = []
    MAX_ITERATIONS = 3

    for iteration in range(MAX_ITERATIONS):
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=messages,
            tools=[RETRIEVER_TOOL_DEFINITION],
            tool_choice="auto",   # agent decides whether to call the tool
            temperature=0.2,
        )

        choice = response.choices[0]
        assistant_message = choice.message

        # No tool call → model has its final answer
        if not assistant_message.tool_calls:
            return {
                "content": assistant_message.content or "",
                "sources": retrieved_sources,
                "tool_calls": None,
            }

        # ── Tool call requested ────────────────────────────────────────────
        # Every tool_call_id must get a matching "tool" reply, or the next
        # OpenAI request is rejected — so we answer each call, even bad ones.
        messages.append(assistant_message)  # type: ignore
        for tool_call in assistant_message.tool_calls:
            tool_result_text = await _run_tool_call(tool_call, user_message, db, retrieved_sources)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result_text,
            })

        # Loop continues → model will now synthesise an answer from the context

    # Hit MAX_ITERATIONS while the model was still calling tools
    last_content = assistant_message.content or "I wasn't able to generate a response."
    return {
        "content": last_content,
        "sources": retrieved_sources,
        "tool_calls": None,
    }


async def _run_tool_call(
    tool_call,
    user_message: str,
    db: AsyncSession,
    retrieved_sources: list[dict],
) -> str:
    """Execute one tool call and return the text to send back to the model.

    New chunks are appended to retrieved_sources (de-duplicated by chunk_id).
    """
    if tool_call.function.name != "retrieve_documents":
        return f"Error: unknown tool '{tool_call.function.name}'."

    try:
        args = json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError:
        args = {}
    if not isinstance(args, dict):
        args = {}
    query = args.get("query") or user_message

    chunks = await retrieve(query, db)

    seen = {s["chunk_id"] for s in retrieved_sources}
    retrieved_sources.extend(c for c in chunks if c["chunk_id"] not in seen)

    if not chunks:
        return "No relevant documents found for this query."
    return _format_chunks_for_prompt(chunks)


def _format_chunks_for_prompt(chunks: list[dict]) -> str:
    """Format retrieved chunks into a clean context block for the model."""
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        source_label = f"{chunk['document_name']}"
        if chunk.get("page_number"):
            source_label += f", page {chunk['page_number']}"
        parts.append(
            f"[Source {i}: {source_label}]\n{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)
