"""GET/PATCH /api/settings — LLM provider selection and encrypted API keys."""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import settings_service
from ..db import get_db
from ..schemas import PatchSettingsRequest, PatchSettingsResponse, SettingsResponse

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)) -> SettingsResponse:
    return SettingsResponse(**settings_service.get_settings(db))


@router.patch("", response_model=PatchSettingsResponse)
def patch_settings(body: PatchSettingsRequest, db: Session = Depends(get_db)):
    try:
        return PatchSettingsResponse(**settings_service.patch_setting(db, body.key, body.value))
    except settings_service.InvalidSettingError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})
