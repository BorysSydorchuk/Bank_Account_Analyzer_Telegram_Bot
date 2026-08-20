"""GET/POST /api/auth/{google/login,google/callback,logout,register,login,
set-password} — real user sign-in. Google (S6-03) and email/password
(S6-04), both in this one file since they're the same user-facing surface.
Distinct from routers/auth.py, which is Enable Banking's bank-session flow
(/api/auth/enable-banking/*) — same /api/auth prefix, disjoint sub-paths,
no route collision.
"""
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER, HTTP_307_TEMPORARY_REDIRECT

from .. import crud
from ..auth.dependency import get_current_user
from ..auth.password import PasswordTooWeakError, hash_password, validate_password_strength, verify_password
from ..db import get_db
from ..google_oauth import GoogleOAuthError, build_authorize_url, exchange_code_for_tokens, fetch_userinfo
from ..models import User
from ..rate_limit import LOGIN_RATE_LIMIT, REGISTER_RATE_LIMIT, limiter
from ..schemas import LoginRequest, RegisterRequest, SetPasswordRequest, UserOut
from ..auth.session import (
    COOKIE_SECURE,
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    create_session,
    destroy_session,
    set_session_cookie,
)

router = APIRouter(prefix="/api/auth", tags=["user-auth"])

# S6-04: a fixed, generic message on every login failure — wrong password
# AND nonexistent email get the exact same text, so the response alone
# never tells a caller which case they hit. Revealing that difference is
# a user-enumeration leak: an attacker could otherwise probe arbitrary
# emails and learn which ones have accounts here.
_INVALID_LOGIN_MESSAGE = "Invalid email or password."

# Hashed once at import time, never displayed or logged — exists only so
# a login attempt against a nonexistent email still runs a real bcrypt
# verify (against this, instead of a real user's hash) rather than
# short-circuiting immediately. Without this, "email doesn't exist" would
# consistently return faster than "email exists, wrong password" (no
# bcrypt call at all vs. one), which is exactly the timing signal a
# user-enumeration attack measures for. Not a complete fix — network
# jitter and the surrounding DB query still leave some signal — but it
# closes the single largest, cheapest-to-exploit gap (a bcrypt call is
# tens of milliseconds; that's the dominant cost being equalized here).
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))

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


@router.post("/register", status_code=201, response_model=UserOut)
@limiter.limit(REGISTER_RATE_LIMIT)
def register(request: Request, body: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> User:
    if crud.get_user_by_email(db, body.email) is not None:
        # Deliberately specific here, unlike login's generic message —
        # register's own existence already confirms "an account can be
        # created," so refusing a duplicate reveals nothing login doesn't
        # already imply; the enumeration concern is specific to *login*
        # silently confirming which emails exist, not to register
        # (a standard, expected behavior every sign-up form has).
        raise HTTPException(status_code=400, detail="An account with that email already exists.")

    try:
        validate_password_strength(body.password)
    except PasswordTooWeakError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = crud.create_user_from_password(db, body.email, hash_password(body.password))
    session_id = create_session(user.id)
    set_session_cookie(response, session_id)
    return user


@router.post("/login", response_model=UserOut)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(request: Request, body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = crud.get_user_by_email(db, body.email)

    # Always runs a real bcrypt verify, whether or not user exists — see
    # _DUMMY_PASSWORD_HASH's docstring above for why. A Google-only
    # account (password_hash is NULL) is treated the same as "wrong
    # password," not "this account can't log in this way" — that
    # distinction is exactly the kind of thing a user-enumeration attempt
    # would want to learn.
    password_hash = user.password_hash if user and user.password_hash else _DUMMY_PASSWORD_HASH
    password_correct = verify_password(body.password, password_hash)

    if user is None or user.password_hash is None or not password_correct:
        raise HTTPException(status_code=401, detail=_INVALID_LOGIN_MESSAGE)

    session_id = create_session(user.id)
    set_session_cookie(response, session_id)
    return user


@router.post("/set-password", status_code=204)
def set_password(
    body: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Sets a real password on the caller's own account — the path a
    Google-only account (password_hash is a locked, never-revealed
    placeholder for the S6-02 bootstrap row, or NULL for any other
    Google-only signup) uses to add password sign-in as a second method.
    Requires an existing session (get_current_user), so this always acts
    on the authenticated caller's own account — there's no email/user_id
    in the request body for it to act on anyone else's.
    """
    try:
        validate_password_strength(body.password)
    except PasswordTooWeakError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    crud.set_password(db, current_user, hash_password(body.password))
