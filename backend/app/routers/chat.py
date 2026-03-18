import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Conversation, Message, MessageRole
from app.schemas import (
    ChatRequest, ChatResponse, ConversationCreate,
    ConversationOut, ConversationListOut, ConversationHistoryOut, MessageOut,
)
from app.services.agent import run_agent

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    conv = Conversation(title=payload.title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/conversations", response_model=ConversationListOut)
async def list_conversations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()
    return ConversationListOut(conversations=list(convs))


@router.get("/conversations/{conv_id}", response_model=ConversationHistoryOut)
async def get_conversation(conv_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    return ConversationHistoryOut(conversation=conv, messages=list(messages))


@router.delete("/conversations/{conv_id}", status_code=204)
async def delete_conversation(conv_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    await db.delete(conv)
    await db.commit()


@router.post("/message", response_model=ChatResponse)
async def send_message(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Main chat endpoint. Steps:
      1. Find or create the conversation
      2. Load conversation history for context
      3. Run the agent (which may call the retriever tool)
      4. Persist user + assistant messages
      5. Return the response with source citations
    """
    # 1. Resolve conversation
    if payload.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == payload.conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        # Auto-create with the first few words of the user's message as title
        title = payload.message[:60] + ("…" if len(payload.message) > 60 else "")
        conversation = Conversation(title=title)
        db.add(conversation)
        await db.flush()

    # 2. Load history (last 20 messages to stay within context limits)
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    recent_messages = list(reversed(history_result.scalars().all()))

    # Convert to OpenAI message format
    history_for_agent = [
        {"role": msg.role.value, "content": msg.content}
        for msg in recent_messages
        if msg.role in (MessageRole.user, MessageRole.assistant)
    ]

    # 3. Run the agent
    agent_result = await run_agent(
        user_message=payload.message,
        conversation_history=history_for_agent,
        db=db,
    )

    # 4. Persist messages
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=payload.message,
    )
    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=agent_result["content"],
        retrieved_chunks=agent_result["sources"] if agent_result["sources"] else None,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    return ChatResponse(
        conversation_id=conversation.id,
        message=MessageOut.model_validate(assistant_msg),
        sources=agent_result["sources"],
    )
