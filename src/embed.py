import os
from pathlib import Path
from fastembed import TextEmbedding

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import chromadb
from chromadb.config import Settings

CHROMA_DIR = "data/chroma_store"
COLLECTION_NAME = "chess_coach"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def get_chroma_client() -> chromadb.PersistentClient:
    """
    Create a persistent ChromaDB client.
    Data saved to disk so we only embed once.
    """
    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False)
    )
    return client


def get_or_create_collection(client: chromadb.PersistentClient):
    """
    Get existing collection or create a new one.
    Uses cosine similarity for semantic search.
    """
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    return collection


def embed_and_store(chunks: list[dict], reset: bool = False) -> None:
    """
    Embed all chunks and store in ChromaDB.

    Uses fastembed instead of sentence-transformers because
    fastembed uses ONNX Runtime which works on Intel Mac
    without requiring PyTorch.

    BAAI/bge-small-en-v1.5 is a high quality retrieval
    model that outperforms all-MiniLM-L6-v2 on most
    semantic search benchmarks.
    """
    client = get_chroma_client()

    if reset:
        print("Resetting collection...")
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = get_or_create_collection(client)

    existing_count = collection.count()
    if existing_count > 0 and not reset:
        print(f"Collection already has {existing_count} chunks.")
        print("Skipping. Use reset=True to rebuild.")
        return

    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = TextEmbedding(EMBEDDING_MODEL)

    ids = []
    embeddings = []
    documents = []
    metadatas = []

    print(f"Embedding {len(chunks)} chunks...")

    for i, chunk in enumerate(chunks):
        chunk_id = (
            f"{chunk['metadata']['source']}_"
            f"chunk_{chunk['metadata']['chunk_id']}"
        )

        # fastembed returns a generator — we take the first result
        embedding = list(model.embed([chunk["text"]]))[0].tolist()

        ids.append(chunk_id)
        embeddings.append(embedding)
        documents.append(chunk["text"])
        metadatas.append(chunk["metadata"])

        if (i + 1) % 10 == 0:
            print(f"  Embedded {i + 1}/{len(chunks)} chunks...")

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    print(f"\nStored {len(chunks)} chunks in ChromaDB")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Location: {CHROMA_DIR}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "src")
    from ingest import load_documents
    from chunk import chunk_documents

    docs = load_documents()
    chunks = chunk_documents(docs)
    embed_and_store(chunks, reset=True)

    client = get_chroma_client()
    collection = get_or_create_collection(client)
    print(f"\nVerification: {collection.count()} chunks in ChromaDB")
