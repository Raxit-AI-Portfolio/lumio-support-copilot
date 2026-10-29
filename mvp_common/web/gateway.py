"""Gateway shared by both frameworks: dummy sign-in, streaming chat page, approvals API.

A framework supplies one function, stream_turn(identity, message, conversation_id): an async generator of
(kind, text) pairs. An empty conversation_id means the user's own ongoing conversation.
"""

import json
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from mvp_common.core.identity import TOKENS, identity_from_token
from mvp_common.tools import approvals
from mvp_common.tools.db import connect, ensure_database
from mvp_common.tools.scope import ToolError

PAGE = Path(__file__).parent / "index.html"
MAX_MESSAGE_LENGTH = 1000
router = APIRouter()


class ChatBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str
    conversation_id: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9_.-]*$")


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    action_hash: str = ""


def current_identity(authorization: str = Header(default="")) -> dict:
    """Read the bearer token and return the identity. No token or a wrong token gives 401."""
    token = authorization.removeprefix("Bearer ").strip()
    conn = connect()
    try:
        return identity_from_token(conn, token)
    except PermissionError:
        raise HTTPException(status_code=401, detail="invalid token")
    finally:
        conn.close()


@router.get("/")
def page() -> FileResponse:
    """Serve the single page."""
    return FileResponse(PAGE)


@router.get("/personas")
def personas() -> dict:
    """List the dummy sign-in tokens so the page can offer them."""
    return {"tokens": list(TOKENS)}


@router.get("/me")
def me(identity: dict = Depends(current_identity)) -> dict:
    """Return who the token belongs to."""
    return {"user_id": identity["user_id"], "role": identity["role"], "tenant_id": identity["tenant_id"]}


@router.get("/approvals")
def pending_approvals(identity: dict = Depends(current_identity)) -> dict:
    """List pending approvals for a lead."""
    conn = connect()
    try:
        return {"approvals": approvals.list_approvals(conn, identity)}
    except ToolError as error:
        raise HTTPException(status_code=403, detail=str(error))
    finally:
        conn.close()


@router.post("/approvals/{approval_id}/decide")
def decide(approval_id: str, body: DecisionBody, identity: dict = Depends(current_identity)) -> dict:
    """A lead approves (with the action hash) or rejects."""
    conn = connect()
    try:
        if body.decision == "approve":
            return approvals.approve_action(conn, identity, approval_id, body.action_hash)
        if body.decision == "reject":
            return approvals.reject_action(conn, identity, approval_id)
        raise HTTPException(status_code=422, detail="decision must be approve or reject")
    except ToolError as error:
        raise HTTPException(status_code=403, detail=str(error))
    finally:
        conn.close()


def sse(kind: str, text: str) -> str:
    """Format one server-sent event."""
    return f"data: {json.dumps({'kind': kind, 'text': text})}\n\n"


def create_app(title: str, stream_turn: Callable) -> FastAPI:
    """Build the app: the shared routes plus /chat, which streams whatever stream_turn yields."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """On start, make sure the database file exists."""
        ensure_database()
        yield

    async def chat_events(identity: dict, message: str, conversation_id: str):
        """Yield status and answer events for one chat turn."""
        try:
            async for kind, text in stream_turn(identity, message, conversation_id):
                yield sse(kind, text)
        except Exception as error:
            print(f"chat error: {type(error).__name__}")
            yield sse("error", "The assistant is not available right now. Please try again.")

    app = FastAPI(title=title, lifespan=lifespan)
    app.include_router(router)

    @app.post("/chat")
    async def chat(body: ChatBody, identity: dict = Depends(current_identity)) -> StreamingResponse:
        """Stream the assistant's reply as server-sent events."""
        if not body.message.strip() or len(body.message) > MAX_MESSAGE_LENGTH:
            raise HTTPException(status_code=422, detail="message is empty or too long")
        return StreamingResponse(
            chat_events(identity, body.message, body.conversation_id), media_type="text/event-stream"
        )

    return app
