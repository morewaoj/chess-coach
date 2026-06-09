import os
import re
from pathlib import Path


def get_doc_type(filename: str) -> str:
    prefix = filename.split("_")[0]
    type_map = {
        "openings": "chess_opening",
        "tactics": "chess_tactics",
        "middlegame": "chess_strategy",
        "attack": "chess_strategy",
        "endgames": "chess_endgame",
    }
    return type_map.get(prefix, "chess_general")


def extract_title(text: str, filename: str) -> str:
    for line in text.split("\n")[:5]:
        if line.startswith("Title:"):
            return line.replace("Title:", "").strip()
    return filename


def clean_text(text: str) -> str:
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        if any(line.startswith(prefix) for prefix in [
            "Title:", "Canonical URL:", "Source type:",
            "Excerpt focus:", "---"
        ]):
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()
    return cleaned


def load_txt(file_path: Path) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def load_documents(raw_dir: str = "documents/raw") -> list[dict]:
    documents = []
    raw_path = Path(raw_dir)

    if not raw_path.exists():
        raise FileNotFoundError(f"Directory not found: {raw_dir}")

    for file_path in sorted(raw_path.iterdir()):
        if file_path.suffix.lower() not in {".txt", ".md"}:
            continue

        filename = file_path.name
        print(f"Loading: {filename}")

        raw_text = load_txt(file_path)
        title = extract_title(raw_text, filename)
        clean = clean_text(raw_text)

        if not clean.strip():
            print(f"  WARNING: {filename} produced empty text")
            continue

        doc = {
            "text": clean,
            "metadata": {
                "source": filename,
                "doc_type": get_doc_type(filename),
                "title": title,
                "file_path": str(file_path),
            }
        }

        documents.append(doc)
        print(f"  OK: {len(clean)} chars, type={doc['metadata']['doc_type']}")

    print(f"\nTotal documents loaded: {len(documents)}")
    return documents


if __name__ == "__main__":
    docs = load_documents()
    print("\n--- SAMPLE OUTPUT ---")
    print(f"Title: {docs[0]['metadata']['title']}")
    print(f"Type: {docs[0]['metadata']['doc_type']}")
    print(f"First 200 chars:")
    print(docs[0]['text'][:200])
