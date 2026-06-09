import sys
sys.path.insert(0, "src")

from fastembed import TextEmbedding
import chromadb
from embed import (
    get_chroma_client,
    get_or_create_collection,
    EMBEDDING_MODEL
)

# Load model and collection once at startup
# This is critical for performance — loading on every
# query would add 15-20 seconds per request.
# Module-level initialization means we pay this cost
# once when the server starts, not on every chess move.
print("Loading embedding model for retrieval...")
_model = TextEmbedding(EMBEDDING_MODEL)
_client = get_chroma_client()
_collection = get_or_create_collection(_client)
print("Retrieval system ready.")


def retrieve(query: str, k: int = 5) -> list[dict]:
    """
    Retrieve top-k most relevant chess knowledge chunks.

    How it works:
    1. Embed the query using the same model used for chunks
       — both must use identical embedding space for
       cosine similarity to be meaningful
    2. ChromaDB finds the k closest vectors using HNSW
       (Hierarchical Navigable Small World) algorithm
    3. Return chunks with text, metadata, and distance scores

    For chess coaching, k=5 gives us enough context to:
    - Identify the opening being played
    - Retrieve relevant tactical patterns
    - Surface trap warnings
    - Explain strategic plans
    Without overwhelming the LLM with too much context.

    Distance scores guide answer confidence:
    - Below 0.4: strong match — answer confidently
    - 0.4-0.6: reasonable match — answer with context
    - Above 0.7: weak match — system may not have info
    """
    query_embedding = list(_model.embed([query]))[0].tolist()

    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"]
    )

    chunks = []
    for i in range(len(results["documents"][0])):
        chunks.append({
            "text": results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"],
            "doc_type": results["metadatas"][0][i]["doc_type"],
            "title": results["metadatas"][0][i]["title"],
            "chunk_id": results["metadatas"][0][i]["chunk_id"],
            "distance": round(results["distances"][0][i], 4)
        })

    return chunks


def print_results(query: str, chunks: list[dict]) -> None:
    """Pretty print retrieval results for inspection."""
    print(f"\nQuery: {query}")
    print("=" * 60)
    for i, chunk in enumerate(chunks):
        print(f"\nResult {i+1}:")
        print(f"  Source: {chunk['source']}")
        print(f"  Type:   {chunk['doc_type']}")
        print(f"  Distance: {chunk['distance']}")
        print(f"  Preview: {chunk['text'][:200]}...")
    print()


if __name__ == "__main__":
    """
    Test retrieval with 3 chess queries before
    connecting to generation layer.

    This is the most important test — if retrieval
    returns wrong chunks, the coach advice will be
    wrong regardless of how good the LLM is.
    """
    test_queries = [
        "I played e4 and my opponent played c5 what is this opening",
        "my knight can fork the king and rook how do I calculate",
        "I am in a king and pawn endgame how do I use opposition"
    ]

    for query in test_queries:
        chunks = retrieve(query, k=5)
        print_results(query, chunks)
        print("-" * 60)
