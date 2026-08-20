"""POST /api/chat — streaming chat grounded in the user's real transaction
data (S4-06)."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import chat_service
from ..agents.providers.base import LLMProvider
from ..agents.registry import ProviderNotConfiguredError
from ..auth.dependency import get_current_user
from ..db import get_db
from ..models import User
from ..rate_limit import CHAT_RATE_LIMIT, limiter
from ..schemas import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _sse_event(data: dict) -> str:
    """Format one Server-Sent Events frame: a JSON payload on a `data:` line
    followed by the blank line SSE requires between events."""
    return f"data: {json.dumps(data)}\n\n"


async def _event_stream(stream, provider: LLMProvider):
    """Forward each chunk from the agent's token stream as its own SSE
    frame, then a final frame carrying token usage — or, if the stream
    raises partway through, a final frame carrying a safe error message
    instead of a truncated response or a leaked traceback."""
    try:
        async for chunk in stream:
            yield _sse_event({"token": chunk, "done": False})
        usage = provider.last_usage or {"input": 0, "output": 0}
        yield _sse_event({"token": "", "done": True, "usage": usage})
    except Exception:
        # Never let a raw exception reach an already-open SSE stream — there's
        # no HTTP status code left to change at this point, so the only way
        # to tell the frontend something went wrong is a final frame it can
        # render as an error instead of silently truncating the reply.
        logger.exception("Chat stream failed mid-response")
        yield _sse_event(
            {
                "token": "",
                "done": True,
                "error": "Something went wrong while generating a response. Please try again.",
            }
        )


@router.post("")
@limiter.limit(CHAT_RATE_LIMIT)
async def chat(
    request: Request,
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Streams the assistant's reply as Server-Sent Events: one
    {"token": "...", "done": false} frame per chunk of text, then a final
    {"token": "", "done": true, "usage": {"input": N, "output": M}} frame.

    The provider lookup and financial-context assembly both happen
    synchronously in chat_service.start_chat_stream before this returns a
    StreamingResponse, so a missing API key is a normal 400 JSON error, not
    a broken stream.
    """
    # S5-07: same pattern as categories' name check — a plain Pydantic
    # min_length would turn this common case (submit, then clear, the
    # input box) into a generic 422 instead of a clear 400.
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message can't be empty.")

    try:
        stream, provider = chat_service.start_chat_stream(
            db, current_user.id, body.message, [m.model_dump() for m in body.history]
        )
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(_event_stream(stream, provider), media_type="text/event-stream")
