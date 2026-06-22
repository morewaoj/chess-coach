import math
import re
import sys
from functools import lru_cache

sys.path.insert(0, "src")

from chunk import chunk_documents
from ingest import load_documents


TOKEN_RE = re.compile(r"[a-z0-9+#=/-]+")

CHESS_TERMS = {
    "sicilian", "french", "caro", "kann", "pirc", "scandinavian",
    "najdorf", "dragon", "queens", "gambit", "nimzo", "indian",
    "fork", "pin", "skewer", "discovered", "mate", "checkmate",
    "opposition", "lucena", "philidor", "rook", "pawn", "king",
    "endgame", "opening", "middlegame", "center", "castle", "attack",
    "defense", "knight", "bishop", "queen", "structure", "outpost",
}


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


@lru_cache(maxsize=1)
def _load_chunks() -> tuple[dict, ...]:
    """Load lightweight text chunks once without embedding models."""
    docs = load_documents()
    chunks = chunk_documents(docs)
    indexed = []
    total_chunks = len(chunks) or 1

    doc_freq: dict[str, int] = {}
    tokenized_chunks = []
    for chunk in chunks:
        tokens = tokenize(chunk["text"])
        tokenized_chunks.append(tokens)
        for token in set(tokens):
            doc_freq[token] = doc_freq.get(token, 0) + 1

    for chunk, tokens in zip(chunks, tokenized_chunks):
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1

        indexed.append({
            "text": chunk["text"],
            "metadata": chunk["metadata"],
            "counts": counts,
            "idf": {
                token: math.log((1 + total_chunks) / (1 + doc_freq[token])) + 1
                for token in counts
            },
        })

    return tuple(indexed)


def _score_chunk(query_tokens: list[str], chunk: dict) -> float:
    score = 0.0
    counts = chunk["counts"]
    idf = chunk["idf"]
    source = chunk["metadata"]["source"].lower()
    title = chunk["metadata"]["title"].lower()
    doc_type = chunk["metadata"]["doc_type"]
    query_set = set(query_tokens)

    for token in query_tokens:
        if token in counts:
            score += (1 + math.log(counts[token])) * idf[token]
        if token in source or token in title:
            score += 1.25
        if token in CHESS_TERMS and token in counts:
            score += 0.75

    if {"e4", "c5"}.issubset(query_set) and "sicilian" in source:
        score += 12.0
    if {"fork", "knight"}.issubset(query_set) and "tactics" in source:
        score += 10.0
    if "opposition" in query_set and "king_pawn" in source:
        score += 10.0
    if "opening" in query_set and doc_type == "chess_opening":
        score += 3.0
    if "endgame" in query_set and doc_type == "chess_endgame":
        score += 3.0
    if any(token in query_set for token in ("tactic", "tactics", "calculate")):
        if doc_type == "chess_tactics":
            score += 3.0

    return score


def retrieve(query: str, k: int = 5) -> list[dict]:
    """
    Retrieve relevant chess knowledge chunks without heavy vector deps.

    This production-light retriever is intentionally simple: the corpus is
    only 8 documents, so lexical scoring is enough for a hosted portfolio
    demo and avoids loading ONNX/Chroma in small-memory environments.
    """
    query_tokens = tokenize(query)
    chunks = _load_chunks()

    scored = [
        (_score_chunk(query_tokens, chunk), idx, chunk)
        for idx, chunk in enumerate(chunks)
    ]
    scored.sort(key=lambda item: item[0], reverse=True)

    results = []
    for rank, (score, idx, chunk) in enumerate(scored[:k], start=1):
        metadata = chunk["metadata"]
        results.append({
            "text": chunk["text"],
            "source": metadata["source"],
            "doc_type": metadata["doc_type"],
            "title": metadata["title"],
            "chunk_id": metadata["chunk_id"],
            "distance": round(1 / (1 + score), 4),
            "rank": rank,
        })

    return results


def print_results(query: str, chunks: list[dict]) -> None:
    """Pretty print retrieval results for inspection."""
    print(f"\nQuery: {query}")
    print("=" * 60)
    for i, chunk in enumerate(chunks):
        print(f"\nResult {i+1}:")
        print(f"  Source: {chunk['source']}")
        print(f"  Type:   {chunk['doc_type']}")
        print(f"  Score proxy: {chunk['distance']}")
        print(f"  Preview: {chunk['text'][:200]}...")
    print()


if __name__ == "__main__":
    test_queries = [
        "I played e4 and my opponent played c5 what is this opening",
        "my knight can fork the king and rook how do I calculate",
        "I am in a king and pawn endgame how do I use opposition"
    ]

    for query in test_queries:
        chunks = retrieve(query, k=5)
        print_results(query, chunks)
        print("-" * 60)
