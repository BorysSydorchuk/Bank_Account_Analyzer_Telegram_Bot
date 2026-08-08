"""GET/POST /api/auth/enable-banking/* — session status and the web re-consent flow.

PSD2 requires the account holder to actively re-consent through their bank at each
renewal (Enable Banking sessions run ~90 days) — no application, including this one,
can silently refresh that consent on the user's behalf. These endpoints replace the
terminal-only flow (`python -m kbc_analyzer.main`) with one the dashboard can drive,
still ending in the user manually completing KBC's own login/consent screen.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..eb_service import EnableBankingError, EnableBankingService
from ..schemas import CallbackRequest, EnableBankingStatus, ReauthorizeResponse
from ..tasks.auth import catch_enable_banking_callback

router = APIRouter(prefix="/api/auth/enable-banking", tags=["auth"])


def get_eb_service() -> EnableBankingService:
    return EnableBankingService()


@router.get("/status", response_model=EnableBankingStatus)
def get_status(eb: EnableBankingService = Depends(get_eb_service)) -> EnableBankingStatus:
    return EnableBankingStatus(**eb.get_session_status())


@router.post("/reauthorize", response_model=ReauthorizeResponse)
def reauthorize(eb: EnableBankingService = Depends(get_eb_service)) -> ReauthorizeResponse:
    # S3-07 Item 2: a background task now catches the redirect automatically
    # (app/eb_callback_server.py) instead of the user copy-pasting it back —
    # the frontend's only remaining job is to open auth_url and poll /status.
    auth_url = eb.get_reauthorize_url()
    catch_enable_banking_callback.delay()
    return ReauthorizeResponse(auth_url=auth_url)


@router.post("/callback", response_model=EnableBankingStatus)
def callback(
    body: CallbackRequest,
    eb: EnableBankingService = Depends(get_eb_service),
):
    """Manual fallback (S2-02) — no longer called by the frontend now that
    reconnecting catches the redirect automatically (S3-07 Item 2), but kept
    as a working escape hatch in case that ever needs bypassing.
    """
    try:
        return EnableBankingStatus(**eb.complete_reauthorization(body.code))
    except EnableBankingError:
        # The generic EnableBankingError handler (main.py) surfaces Enable Banking's
        # raw error JSON, which is fine for a background sync failure but not for a
        # message shown directly under a form the user just filled in — the most
        # common cause here is a stale/already-used code, so say that plainly.
        return JSONResponse(
            status_code=400,
            content={
                "message": (
                    "That authorization code wasn't accepted — it may have expired or "
                    "already been used. Click Reconnect to start over."
                )
            },
        )
