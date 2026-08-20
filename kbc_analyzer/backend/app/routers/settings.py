"""GET/PATCH /api/settings — LLM provider selection and encrypted API keys."""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import settings_service
from ..agents.providers.claude import ClaudeProvider
from ..agents.providers.gemini import GeminiProvider
from ..agents.registry import invalidate_provider_cache
from ..auth.dependency import get_current_user
from ..db import get_db
from ..models import User
from ..schemas import (
    PatchSettingsRequest,
    PatchSettingsResponse,
    SettingsResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> SettingsResponse:
    return SettingsResponse(**settings_service.get_settings(db, current_user.id))


@router.patch("", response_model=PatchSettingsResponse)
def patch_settings(
    body: PatchSettingsRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    try:
        result = settings_service.patch_setting(db, current_user.id, body.key, body.value)
    except settings_service.InvalidSettingError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})
    # S4-09 Item 3: not just an llm_provider switch — a key edit under the
    # same provider name must drop the cache too, or get_provider() would
    # keep serving an instance built from the old key.
    invalidate_provider_cache()
    return PatchSettingsResponse(**result)


def _connection_error_message(exc: Exception) -> str:
    """Provider SDKs each raise a different exception shape — dig out the
    clean, human-readable reason each one actually carries (Gemini's
    `.message`, Anthropic's `.body["error"]["message"]`) instead of showing
    the raw exception repr, which for both SDKs is a long nested dict string.
    """
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        nested = body.get("error")
        if isinstance(nested, dict) and nested.get("message"):
            return nested["message"]
    message = getattr(exc, "message", None)
    if isinstance(message, str) and message:
        return message
    return str(exc)


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    body: TestConnectionRequest, current_user: User = Depends(get_current_user)
) -> TestConnectionResponse:
    """Tests the key currently in the form — deliberately independent of
    Save, so a key can be checked before committing to storing it. Gated
    behind auth (S6-06's blanket "every endpoint requires authentication"
    criterion) but not scoped — it takes the key directly in the request
    body and never touches storage, so there's nothing to scope.
    """
    if not body.api_key.strip():
        return TestConnectionResponse(connected=False, error_message="Enter an API key first.")

    provider = GeminiProvider(body.api_key) if body.provider == "gemini" else ClaudeProvider(body.api_key)
    try:
        await provider.test_connection()
    except Exception as exc:
        return TestConnectionResponse(connected=False, error_message=_connection_error_message(exc))
    return TestConnectionResponse(connected=True)
