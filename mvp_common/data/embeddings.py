"""Vertex AI embeddings: one text in, one 768-number vector out."""

import math

from google import genai
from google.genai import types

from mvp_common.core.config import EMBED_DIMENSIONS, get_setting


def normalize(vector: list[float]) -> list[float]:
    """Scale a vector to length 1, so a dot product equals cosine similarity (needed for 768-dim Gemini output)."""
    length = math.sqrt(sum(x * x for x in vector))
    return [x / length for x in vector] if length else vector


def make_client() -> genai.Client:
    """Create the Vertex AI client. Creating one takes seconds, so loops make it once and pass it in."""
    return genai.Client(
        vertexai=True,
        project=get_setting("GOOGLE_CLOUD_PROJECT"),
        location=get_setting("EMBED_LOCATION", "us-central1"),
    )


def embed_text(text: str, task_type: str, client: genai.Client | None = None) -> list[float]:
    """Embed one text. task_type is RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY."""
    client = client or make_client()
    config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBED_DIMENSIONS)
    model = get_setting("EMBED_MODEL", "gemini-embedding-001")
    reply = client.models.embed_content(model=model, contents=text, config=config)
    return normalize(list(reply.embeddings[0].values))
