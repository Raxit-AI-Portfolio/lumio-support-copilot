"""Build the KB index: chunk every KB file, embed each chunk, write one JSON file.

Run from the repo root: python -m mvp_common.data.ingest
"""

import json

from mvp_common.core.config import INDEX_FILE, KB_DIR
from mvp_common.data.chunking import make_chunks
from mvp_common.data.embeddings import embed_text, make_client


def build_index() -> list[dict]:
    """Return all chunks with a "vector" field."""
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        chunks.extend(make_chunks(path.read_text(encoding="utf-8")))
    client = make_client()
    for chunk in chunks:
        text = f"{chunk['title']} - {chunk['section']}\n{chunk['text']}"
        chunk["vector"] = embed_text(text, "RETRIEVAL_DOCUMENT", client)
    return chunks


def main() -> None:
    """Write the index file and print one summary line."""
    chunks = build_index()
    INDEX_FILE.write_text(json.dumps(chunks), encoding="utf-8")
    print(f"indexed {len(chunks)} chunks from {len({c['doc_id'] for c in chunks})} docs -> {INDEX_FILE.name}")


if __name__ == "__main__":
    main()
