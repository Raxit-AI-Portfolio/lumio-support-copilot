"""Guardrails shared by both frameworks: Model Armor screening and the citation check (BR-KNW-02, ADR-08)."""

import re

import google.auth
import httpx
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request

from mvp_common.core.config import get_setting

CUSTOMER_TOOLS = ["kb_search", "get_ticket", "list_tickets", "create_ticket", "add_comment"]
ALLOWED_TOOLS = {
    "customer": CUSTOMER_TOOLS,
    "agent": CUSTOMER_TOOLS + ["propose_action"],
    "lead": CUSTOMER_TOOLS + ["propose_action", "queue_summary"],
}
MAX_CALLS_PER_TURN = 5
SCREENED_TOOLS = ["kb_search", "get_ticket"]
MAX_SCREEN_CHARS = 10000
BRACKET = re.compile(r"\[([^\[\]]*#[^\[\]]*)\]")


def call_model_armor(template: str, text: str) -> dict:
    """Send text to Model Armor and return its reply. The template is projects/P/locations/L/templates/T."""
    location = template.split("/")[3]
    url = f"https://modelarmor.{location}.rep.googleapis.com/v1/{template}:sanitizeUserPrompt"
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    headers = {"Authorization": f"Bearer {credentials.token}"}
    if get_setting("GOOGLE_CLOUD_PROJECT"):
        headers["x-goog-user-project"] = get_setting("GOOGLE_CLOUD_PROJECT")
    reply = httpx.post(url, json={"userPromptData": {"text": text}}, headers=headers, timeout=10)
    reply.raise_for_status()
    return reply.json()


def describe_failure(error: Exception) -> str:
    """Return the error type and, for an HTTP error, the status and Google's message (never the user's text)."""
    if isinstance(error, httpx.HTTPStatusError):
        message = error.response.json().get("error", {}).get("message", "")
        return f"HTTP {error.response.status_code} {message}"[:300]
    return f"{type(error).__name__} {error}"[:300]


def screen_text(text: str) -> bool:
    """Return True if the text may pass. Off when no template is set; blocks if the screen itself fails."""
    template = get_setting("MODEL_ARMOR_TEMPLATE")
    if not template:
        return True
    try:
        reply = call_model_armor(template, text[:MAX_SCREEN_CHARS])
        return reply["sanitizationResult"]["filterMatchState"] != "MATCH_FOUND"
    except (httpx.HTTPError, GoogleAuthError, KeyError) as error:
        print(f"model armor screen failed, blocking: {describe_failure(error)}")
        return False


def clean_citations(answer: str, retrieved_ids: list[str]) -> tuple[str, list[str]]:
    """Remove cited ids that were not retrieved this turn. Returns (clean answer, removed ids)."""
    removed = []
    for match in BRACKET.findall(answer):
        ids = [part.strip() for part in match.split(",")]
        known = [one for one in ids if one in retrieved_ids]
        if len(known) == len(ids):
            continue
        removed.extend(one for one in ids if one not in retrieved_ids)
        replacement = "[" + ", ".join(known) + "]" if known else ""
        answer = answer.replace("[" + match + "]", replacement)
    return answer.strip(), removed
