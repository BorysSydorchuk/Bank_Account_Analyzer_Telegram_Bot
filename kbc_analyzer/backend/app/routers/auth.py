"""GET/POST /api/auth/enable-banking/* — session status and the web re-consent flow.

PSD2 requires the account holder to actively re-consent through their bank at each
renewal (Enable Banking sessions run ~90 days) — no application, including this one,
can silently refresh that consent on the user's behalf. These endpoints replace the
terminal-only flow (`python -m kbc_analyzer.main`) with one the dashboard can drive,
still ending in the user manually completing KBC's own login/consent screen.

S6-06: all three endpoints require require_enable_banking_owner — the single
eb_session.json connection belongs to exactly one real account
(ENABLE_BANKING_OWNER_EMAIL) until Sprint 7's per-user bank session storage.
"""
import secrets

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from ..auth.dependency import require_enable_banking_owner
from ..auth.session import COOKIE_SECURE
from ..eb_service import EnableBankingError, EnableBankingService
from ..models import User
from ..schemas import CallbackRequest, EnableBankingStatus, ReauthorizeResponse
from ..tasks.auth import catch_enable_banking_callback

router = APIRouter(prefix="/api/auth/enable-banking", tags=["auth"])

# S7-04, mirrors user_auth.py's oauth_state pattern exactly. Previously
# Enable Banking's own request carried a state value that was generated and
# immediately discarded ("not checked by us") — harmless while the callback
# only existed on localhost, a real CSRF gap once it's a public URL: without
# this, a forged https://mymble.be/api/auth/enable-banking/callback?code=...
# link could trick an already-logged-in victim's browser into completing
# reauthorization with an attacker-supplied code.
_EB_STATE_COOKIE_NAME = "eb_oauth_state"
_EB_STATE_COOKIE_TTL_SECONDS = 10 * 60  # generous for a human to complete the bank's own login/consent screen


def get_eb_service() -> EnableBankingService:
    return EnableBankingService()


@router.get("/status", response_model=EnableBankingStatus)
def get_status(
    eb: EnableBankingService = Depends(get_eb_service),
    current_user: User = Depends(require_enable_banking_owner),
) -> EnableBankingStatus:
    return EnableBankingStatus(**eb.get_session_status())


@router.post("/reauthorize", response_model=ReauthorizeResponse)
def reauthorize(
    response: Response,
    eb: EnableBankingService = Depends(get_eb_service),
    current_user: User = Depends(require_enable_banking_owner),
) -> ReauthorizeResponse:
    # S3-07 Item 2: a background task now catches the redirect automatically
    # (app/eb_callback_server.py) instead of the user copy-pasting it back —
    # the frontend's only remaining job is to open auth_url and poll /status.
    #
    # S7-04: state is generated here (not left to enablebanking.py's own
    # throwaway default) and stashed in a cookie on this JSON response —
    # this endpoint returns auth_url for the frontend to open in a new tab
    # rather than redirecting itself, so the cookie has to be set here,
    # unlike user_auth.py's server-side-redirect equivalent.
    state = secrets.token_urlsafe(24)
    auth_url = eb.get_reauthorize_url(state)
    response.set_cookie(
        key=_EB_STATE_COOKIE_NAME,
        value=state,
        max_age=_EB_STATE_COOKIE_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    catch_enable_banking_callback.delay()
    return ReauthorizeResponse(auth_url=auth_url)


@router.post("/callback", response_model=EnableBankingStatus)
def callback(
    body: CallbackRequest,
    eb: EnableBankingService = Depends(get_eb_service),
    current_user: User = Depends(require_enable_banking_owner),
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


_CONFIRMATION_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Mymble</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
    background: #F8FAFC;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #1E293B;
  }}
  .card {{
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 16px;
    padding: 48px 40px;
  }}
  .wordmark {{
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: #2563EB;
    margin-bottom: 8px;
  }}
  .icon {{
    width: 64px;
    height: 64px;
    border-radius: 999px;
    background: {icon_bg};
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  h1 {{ font-size: 22px; font-weight: 600; color: #0F172A; }}
  p {{ font-size: 15px; color: #64748B; }}
</style>
</head>
<body>
  <div class="card">
    <div class="wordmark">Mymble</div>
    <div class="icon">{icon_svg}</div>
    <h1>{heading}</h1>
    <p>{message}</p>
  </div>
</body>
</html>"""

_SUCCESS_ICON = (
    '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#16A34A" '
    'stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M20 6L9 17l-5-5"/></svg>'
)
_ERROR_ICON = (
    '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#DC2626" '
    'stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
    '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
)


@router.get("/callback", response_class=HTMLResponse)
def callback_redirect(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    eb: EnableBankingService = Depends(get_eb_service),
    current_user: User = Depends(require_enable_banking_owner),
) -> HTMLResponse:
    """S7-04: the real production redirect target — Enable Banking's own
    browser-redirect GET request lands here directly, over the app's real
    domain. Replaces the mkcert-based local catcher server
    (`app/eb_callback_server.py`), which only ever worked because local dev
    could run its own temporary HTTPS listener on a port the bank's
    redirect could reach; a real domain behind an ALB doesn't need that —
    this route IS the reachable HTTPS endpoint, no separate server/process
    required. `code`/`state` arrive as query params on the redirect, not a
    JSON body (contrast the POST /callback fallback above, which the
    frontend calls with a manually-pasted code).
    """
    response.delete_cookie(_EB_STATE_COOKIE_NAME)  # single-use, same as user_auth.py's oauth_state

    expected_state = request.cookies.get(_EB_STATE_COOKIE_NAME)
    if not state or not expected_state or state != expected_state:
        # Missing/mismatched state: either a forged callback (CSRF — see the
        # module docstring above the cookie constants) or a genuinely stale
        # link (cookie already expired/cleared by a prior attempt). Same
        # response either way — nothing here should distinguish the two for
        # an attacker's benefit.
        return HTMLResponse(
            _CONFIRMATION_PAGE.format(
                icon_bg="#FEE2E2",
                icon_svg=_ERROR_ICON,
                heading="Bank connection failed",
                message="This link is no longer valid. Close this tab and click Reconnect to try again.",
            ),
            status_code=400,
        )
    if not code:
        return HTMLResponse(
            _CONFIRMATION_PAGE.format(
                icon_bg="#FEE2E2",
                icon_svg=_ERROR_ICON,
                heading="Bank connection failed",
                message="No authorization code was received. Close this tab and click Reconnect to try again.",
            ),
            status_code=400,
        )
    try:
        eb.complete_reauthorization(code)
    except EnableBankingError:
        return HTMLResponse(
            _CONFIRMATION_PAGE.format(
                icon_bg="#FEE2E2",
                icon_svg=_ERROR_ICON,
                heading="Bank connection failed",
                message="That authorization code wasn't accepted — it may have expired or already been used.",
            ),
            status_code=400,
        )
    return HTMLResponse(
        _CONFIRMATION_PAGE.format(
            icon_bg="#DCFCE7",
            icon_svg=_SUCCESS_ICON,
            heading="Bank connected successfully",
            message="You can close this tab and return to the app.",
        )
    )
