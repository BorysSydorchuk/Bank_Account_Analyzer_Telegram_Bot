"""GET/POST /api/auth/{google/login,google/callback,logout} — real user
sign-in (S6-03: Google only; email/password is S6-04). Distinct from
routers/auth.py, which is Enable Banking's bank-session flow
(/api/auth/enable-banking/*) — same /api/auth prefix, disjoint sub-paths,
no route collision.
"""
import os
import secrets

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER, HTTP_307_TEMPORARY_REDIRECT

from .. import crud
from ..db import get_db
from ..google_oauth import GoogleOAuthError, build_authorize_url, exchange_code_for_tokens, fetch_userinfo
from ..auth.session import (
    COOKIE_SECURE,
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    create_session,
    destroy_session,
    set_session_cookie,
)

router = APIRouter(prefix="/api/auth", tags=["user-auth"])

_STATE_COOKIE_NAME = "oauth_state"
_STATE_COOKIE_TTL_SECONDS = 10 * 60  # generous for a human to actually complete Google's consent screen


def _frontend_origin() -> str:
    return os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")


@router.get("/google/login")
def google_login() -> RedirectResponse:
    # A fresh, unguessable value per attempt — compared against what the
    # callback receives to prove this callback is answering *this*
    # browser's own request, not a forged/replayed one (see
    # google_oauth.build_authorize_url's docstring).
    state = secrets.token_urlsafe(24)
    try:
        authorize_url = build_authorize_url(state)
    except GoogleOAuthError:
        # Missing/misconfigured GOOGLE_CLIENT_ID — a real, expected state
        # before Borys adds real credentials (S6-03), and after that only
        # a deployment misconfiguration. Either way this is the same
        # "can't sign in right now" shape as any other Google-side
        # failure, not a 500 with a raw traceback (CLAUDE.md's error
        # handling rule) — routed through the same /login?error= page.
        return RedirectResponse(
            f"{_frontend_origin()}/login?error=google_sign_in_failed", status_code=HTTP_303_SEE_OTHER
        )

    redirect = RedirectResponse(authorize_url, status_code=HTTP_307_TEMPORARY_REDIRECT)
    redirect.set_cookie(
        key=_STATE_COOKIE_NAME,
        value=state,
        max_age=_STATE_COOKIE_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    return redirect


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    error_redirect = RedirectResponse(
        f"{_frontend_origin()}/login?error=google_sign_in_failed", status_code=HTTP_303_SEE_OTHER
    )

    expected_state = request.cookies.get(_STATE_COOKIE_NAME)
    if not code or not state or not expected_state or state != expected_state:
        # Missing code (user denied consent), or a state mismatch (CSRF
        # attempt, expired attempt, or a stale tab replaying an old
        # callback URL) — all treated the same way: back to /login, no
        # session created.
        error_redirect.delete_cookie(_STATE_COOKIE_NAME)
        return error_redirect

    try:
        tokens = exchange_code_for_tokens(code)
        profile = fetch_userinfo(tokens["access_token"])
    except GoogleOAuthError:
        error_redirect.delete_cookie(_STATE_COOKIE_NAME)
        return error_redirect

    google_id = profile["sub"]
    email = profile["email"]
    display_name = profile.get("name")

    user = crud.get_user_by_google_id(db, google_id)
    if user is None:
        existing = crud.get_user_by_email(db, email)
        if existing is None:
            user = crud.create_user_from_google(db, google_id, email, display_name)
        elif existing.google_id is None:
            # Account-linking case: a password-registered account with
            # this exact (Google-verified) email, never linked to Google
            # before — attach this Google identity to it rather than
            # creating a second row for the same person.
            user = crud.link_google_id(db, existing, google_id)
        else:
            # existing.google_id is set to some *other* value — this
            # email is already linked to a different Google account than
            # the one completing this flow. Shouldn't happen under normal
            # use (get_user_by_google_id above would have found it first
            # if it were the same account); treated as a failed sign-in
            # rather than silently repointing an existing link.
            error_redirect.delete_cookie(_STATE_COOKIE_NAME)
            return error_redirect

    session_id = create_session(user.id)
    redirect = RedirectResponse(_frontend_origin(), status_code=HTTP_303_SEE_OTHER)
    redirect.delete_cookie(_STATE_COOKIE_NAME)
    set_session_cookie(redirect, session_id)
    return redirect


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        destroy_session(session_id)
    clear_session_cookie(response)
