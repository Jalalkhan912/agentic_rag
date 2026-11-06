"""Tests for the agent loop with a fake OpenAI client and retriever."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import agent


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id, type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _response(content=None, tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _chunk(chunk_id):
    return {
        "chunk_id": chunk_id, "content": f"text {chunk_id}", "page_number": 1,
        "document_name": "doc.pdf", "document_id": "d1", "similarity_score": 0.9,
    }


def _fake_client(*responses):
    create = AsyncMock(side_effect=list(responses))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, create


@pytest.mark.asyncio
async def test_answers_directly_without_tool():
    client, _ = _fake_client(_response(content="Hi there"))
    with patch.object(agent, "get_openai_client", return_value=client):
        result = await agent.run_agent("hello", [], db=None)
    assert result == {"content": "Hi there", "sources": [], "tool_calls": None}


@pytest.mark.asyncio
async def test_every_tool_call_gets_a_reply_and_sources_are_deduplicated():
    client, create = _fake_client(
        _response(tool_calls=[
            _tool_call("c1", "retrieve_documents", '{"query": "refunds"}'),
            _tool_call("c2", "retrieve_documents", "not json"),
            _tool_call("c3", "some_other_tool", "{}"),
        ]),
        _response(content="Answer"),
    )
    retrieve = AsyncMock(return_value=[_chunk("a"), _chunk("b")])

    with patch.object(agent, "get_openai_client", return_value=client), \
         patch.object(agent, "retrieve", retrieve):
        result = await agent.run_agent("what about refunds?", [], db=None)

    assert result["content"] == "Answer"
    assert [s["chunk_id"] for s in result["sources"]] == ["a", "b"]

    # Bad JSON falls back to the user's message as the query
    assert retrieve.await_args_list[1].args[0] == "what about refunds?"

    # The second model call must contain a tool reply for every tool_call_id
    second_messages = create.await_args_list[1].kwargs["messages"]
    replied = [m["tool_call_id"] for m in second_messages if isinstance(m, dict) and m.get("role") == "tool"]
    assert replied == ["c1", "c2", "c3"]


@pytest.mark.asyncio
async def test_none_content_becomes_empty_string():
    client, _ = _fake_client(_response(content=None))
    with patch.object(agent, "get_openai_client", return_value=client):
        result = await agent.run_agent("hello", [], db=None)
    assert result["content"] == ""
