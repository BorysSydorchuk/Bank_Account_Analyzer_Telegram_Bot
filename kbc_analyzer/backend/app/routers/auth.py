"""GET/POST /api/auth/enable-banking/* — session status and the web re-consent flow.

PSD2 requires the account holder to actively re-consent through their bank at each
renewal (Enable Banking sessions run ~90 days) — no application, including this one,
can silently refresh that consent on the user's behalf. These endpoints replace the
terminal-only flow (`python -m kbc_analyzer.main`) with one the dashboard can drive,
still ending in the user manually completing KBC's own login/consent screen.

S7-06: all endpoints use per-user auth — any authenticated user can establish and
manage their own independent Enable Banking connection, replacing S6-06's
require_enable_banking_owner gate (which restricted this to a single named account
because the single eb_session.json file could only ever hold one connection at a
time). Session state lives in enable_banking_sessions, one encrypted row per
user_id (app/eb_session_store.py) — EnableBankingService is constructed per
request, scoped to current_user.id, so one user's session can never be read or
overwritten by another's request.

S7-09: gated behind require_verified_email, not plain get_current_user — Enable
Banking is the one feature this project's deliberate unverified-account access
policy restricts (see app/auth/dependency.py's require_verified_email docstring
and ARCHITECTURE.md's Auth section).
"""
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from ..auth.dependency import require_verified_email
from ..auth.session import COOKIE_SECURE
from ..db import get_db
from ..eb_service import EnableBankingError, EnableBankingService
from ..models import User
from ..schemas import CallbackRequest, EnableBankingStatus, ReauthorizeResponse

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

# S7-06: now that any authenticated user can reauthorize their own Enable
# Banking connection (not just one named owner account), the state cookie
# alone is no longer enough — it proves the callback belongs to *a*
# browser that started /reauthorize, but not that it's still the *same
# user's* browser. Mirrors user_auth.py's oauth_link_user_id cookie
# (Google account-linking, S6-07) exactly, for the same reason: without
# this, a user who starts reauthorizing, then logs out and back in as a
# different account in the same browser before finishing KBC's consent
# screen, would have the callback silently complete against whichever
# account happens to be logged in when the redirect lands — attaching
# their bank connection to the wrong user.
_EB_USER_COOKIE_NAME = "eb_oauth_user_id"


def get_eb_service(db: Session = Depends(get_db), current_user: User = Depends(require_verified_email)) -> EnableBankingService:
    return EnableBankingService(db, current_user.id)


@router.get("/status", response_model=EnableBankingStatus)
def get_status(
    eb: EnableBankingService = Depends(get_eb_service),
    current_user: User = Depends(require_verified_email),
) -> EnableBankingStatus:
    return EnableBankingStatus(**eb.get_session_status())


@router.post("/reauthorize", response_model=ReauthorizeResponse)
def reauthorize(
    response: Response,
    eb: EnableBankingService = Depends(get_eb_service),
    current_user: User = Depends(require_verified_email),
) -> ReauthorizeResponse:
    # S7-04: Enable Banking's redirect now lands directly on GET /callback
    # below, over the real production domain — no background task or local
    # catcher server needed (S3-07 Item 2's mkcert-based one is retired,
    # see ARCHITECTURE.md). The frontend's only remaining job is to open
    # auth_url and poll /status.
    #
    # state is generated here (not left to enablebanking.py's own
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
    # S7-06: binds this reauthorize attempt to the user who started it —
    # see the module-level comment on _EB_USER_COOKIE_NAME above.
    response.set_cookie(
        key=_EB_USER_COOKIE_NAME,
        value=str(current_user.id),
        max_age=_EB_STATE_COOKIE_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    return ReauthorizeResponse(auth_url=auth_url)


@router.post("/callback", response_model=EnableBankingStatus)
def callback(
    body: CallbackRequest,
    eb: EnableBankingService = Depends(get_eb_service),
    current_user: User = Depends(require_verified_email),
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
    current_user: User = Depends(require_verified_email),
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
    response.delete_cookie(_EB_USER_COOKIE_NAME)  # S7-06, same single-use reasoning

    expected_state = request.cookies.get(_EB_STATE_COOKIE_NAME)
    expected_user_id = request.cookies.get(_EB_USER_COOKIE_NAME)
    state_ok = bool(state) and bool(expected_state) and state == expected_state
    # S7-06: the callback must be completing for the same user who started
    # it (see _EB_USER_COOKIE_NAME's module-level comment) — current_user
    # here is resolved from the ordinary session cookie, which could belong
    # to a different account than the one that clicked Reconnect if the
    # browser switched accounts mid-flow.
    user_ok = bool(expected_user_id) and UUID(expected_user_id) == current_user.id
    if not state_ok or not user_ok:
        # Missing/mismatched state, or a session that no longer belongs to
        # the user who started this reauthorization: either a forged
        # callback (CSRF — see the module docstring above the cookie
        # constants) or a genuinely stale link (cookies already
        # expired/cleared by a prior attempt, or an account switch
        # mid-flow). Same response either way — nothing here should
        # distinguish the cases for an attacker's benefit.
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
