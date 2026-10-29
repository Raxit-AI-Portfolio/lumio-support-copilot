"""KB search with the access_group filter (BR-KNW-01). The filter comes from the role, never from the model."""

import json
import math

from mvp_common.core.config import INDEX_FILE, get_setting
from mvp_common.data.embeddings import embed_text
from mvp_common.data.vector_search import VectorIndex

KB_MIN_SCORE = 0.69
ALLOWED_GROUPS = {
    "customer": ["public", "customer"],
    "agent": ["public", "customer", "internal"],
    "lead": ["public", "customer", "internal"],
}


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def rank_chunks(query_vector: list[float], chunks: list[dict], role: str, top_k: int = 5) -> list[dict]:
    """Return the top_k chunks the role may see, best first, each with a "score" and no vector."""
    allowed = ALLOWED_GROUPS.get(role, [])
    scored = []
    for chunk in chunks:
        if chunk["access_group"] not in allowed:
            continue
        hit = {key: value for key, value in chunk.items() if key != "vector"}
        hit["score"] = cosine(query_vector, chunk["vector"])
        scored.append(hit)
    scored.sort(key=lambda hit: hit["score"], reverse=True)
    return scored[:top_k]


def search_kb(question: str, role: str, top_k: int = 5, client=None) -> list[dict]:
    """Embed the question and search as the given role: Vector Search if USE_VECTOR_SEARCH=1, else the index file."""
    query_vector = embed_text(question, "RETRIEVAL_QUERY", client)
    if get_setting("USE_VECTOR_SEARCH") == "1":
        return VectorIndex().search(query_vector, ALLOWED_GROUPS.get(role, []), top_k)
    chunks = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return rank_chunks(query_vector, chunks, role, top_k)
