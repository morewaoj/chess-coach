from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_documents(documents: list[dict],
                    chunk_size: int = 800,
                    chunk_overlap: int = 100) -> list[dict]:
    """
    Split chess documents into chunks for embedding.

    Why these settings for chess content:
    - chunk_size=800: chess explanations need enough context
      to be meaningful. A tactical pattern or opening idea
      requires at least a full paragraph to be retrievable.
    - chunk_overlap=100: ensures move sequences that span
      paragraph boundaries are captured in at least one chunk.
    - RecursiveCharacterTextSplitter: respects paragraph
      boundaries first, then sentences — keeps chess
      explanations intact rather than splitting mid-idea.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks = []

    for doc in documents:
        chunks = splitter.split_text(doc["text"])

        for i, chunk_text in enumerate(chunks):
            if not chunk_text.strip():
                continue

            chunk_metadata = doc["metadata"].copy()
            chunk_metadata["chunk_id"] = i
            chunk_metadata["total_chunks"] = len(chunks)

            all_chunks.append({
                "text": chunk_text.strip(),
                "metadata": chunk_metadata
            })

    return all_chunks


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "src")
    from ingest import load_documents

    docs = load_documents()
    chunks = chunk_documents(docs)

    print(f"\nTotal chunks: {len(chunks)}")
    print(f"Average per document: {len(chunks) / len(docs):.1f}")

    print("\n--- 5 SAMPLE CHUNKS ---")
    for idx in [0, 5, 10, 15, 20]:
        if idx < len(chunks):
            chunk = chunks[idx]
            print(f"\nChunk {idx}:")
            print(f"  Source: {chunk['metadata']['source']}")
            print(f"  Type: {chunk['metadata']['doc_type']}")
            print(f"  Chars: {len(chunk['text'])}")
            print(f"  Preview: {chunk['text'][:150]}...")
