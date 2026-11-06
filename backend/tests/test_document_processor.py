"""Unit tests for text extraction and chunking (no DB, no network)."""
from app.services.document_processor import chunk_text, extract_text, _tokenizer


def test_chunk_text_short_text_is_single_chunk():
    chunks = chunk_text("hello world", chunk_size=50, overlap=10)
    assert len(chunks) == 1
    assert chunks[0][0] == "hello world"


def test_chunk_text_respects_size_and_overlap():
    text = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_text(text, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    assert all(count <= 100 for _, count in chunks)

    # Consecutive chunks share `overlap` tokens
    first = _tokenizer.encode(chunks[0][0])
    second = _tokenizer.encode(chunks[1][0])
    assert first[-20:] == second[:20]


def test_chunk_text_empty_string():
    assert chunk_text("", chunk_size=100, overlap=20) == []


def test_extract_text_strips_nul_bytes(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_bytes(b"abc\x00def")
    [(text, page)] = extract_text(f, "txt")
    assert text == "abcdef"
    assert page == 1
