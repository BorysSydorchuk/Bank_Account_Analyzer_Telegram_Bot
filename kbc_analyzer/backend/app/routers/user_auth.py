"""GET/POST /api/auth/{google/login,google/link,google/callback,logout,
register,login,set-password} — real user sign-in. Google (S6-03) and
email/password (S6-04), both in this one file since they're the same
user-facing surface. Distinct from routers/auth.py, which is Enable
Banking's bank-session flow (/api/auth/enable-banking/*) — same
/api/auth prefix, disjoint sub-paths, no route collision.

google/link (S6-07 finding 1) is the only route that may ever attach a
google_id to an existing account — see _LINK_INTENT_COOKIE_NAME's
docstring below for the account-takeover path this closes.
"""
import os
import secrets
from uuid import UUID

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

# S6-07 finding 1 (priority-zero, real account-takeover path): the linking
# flow is now split into two, and this cookie is what tells the shared
# callback which one it's answering. Set only by the authenticated
# /google/link route below, never by the plain, unauthenticated
# /google/login — so its mere presence, combined with the state check
# already in place, is what makes linking an explicit, authenticated act
# instead of something a sign-in can trigger as a side effect.
#
# INVARIANT (do not remove): a Google sign-in must never implicitly attach
# to an existing password-registered account just because the emails
# match. Before this fix, google_callback treated "email matches, no
# google_id set yet" as an unconditional linking case — an attacker could
# register a password account under a victim's real email (no email
# verification exists in this app), and the *victim's own, legitimate*
# Google sign-in would then silently attach to that attacker-controlled
# row, leaving the attacker with standing password access to the victim's
# account and data. Linking must only ever happen while the linking
# user is already authenticated as themselves (this cookie's whole
# purpose) — see docs/verification_debt.md and ARCHITECTURE.md's Auth
# section for the full incident writeup.
_LINK_INTENT_COOKIE_NAME = "oauth_link_user_id"


def _frontend_origin() -> str:
    return os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")


def _google_redirect(state: str) -> RedirectResponse:
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
    return RedirectResponse(authorize_url, status_code=HTTP_307_TEMPORARY_REDIRECT)


@router.get("/google/login")
def google_login() -> RedirectResponse:
    # A fresh, unguessable value per attempt — compared against what the
    # callback receives to prove this callback is answering *this*
    # browser's own request, not a forged/replayed one (see
    # google_oauth.build_authorize_url's docstring).
    state = secrets.token_urlsafe(24)
    redirect = _google_redirect(state)
    redirect.set_cookie(
        key=_STATE_COOKIE_NAME,
        value=state,
        max_age=_STATE_COOKIE_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    return redirect


@router.get("/google/link")
def google_link(current_user: User = Depends(get_current_user)) -> RedirectResponse:
    """S6-07 finding 1 — the *only* legitimate way an existing account ever
    gains a `google_id`, other than signing up fresh with Google in the
    first place. Requires an active session (get_current_user): the
    caller must already be authenticated as themselves — via password,
    since that's the only sign-in method that doesn't already involve
    Google — before this can attach a Google identity to their account.
    google_callback below only treats a callback as a linking action when
    it carries this route's own cookie, never on email-matching alone.
    """
    state = secrets.token_urlsafe(24)
    redirect = _google_redirect(state)
    redirect.set_cookie(
        key=_STATE_COOKIE_NAME,
        value=state,
        max_age=_STATE_COOKIE_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    redirect.set_cookie(
        key=_LINK_INTENT_COOKIE_NAME,
        value=str(current_user.id),
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

    def _clear_oauth_cookies(response: RedirectResponse) -> RedirectResponse:
        response.delete_cookie(_STATE_COOKIE_NAME)
        response.delete_cookie(_LINK_INTENT_COOKIE_NAME)
        return response

    expected_state = request.cookies.get(_STATE_COOKIE_NAME)
    if not code or not state or not expected_state or state != expected_state:
        # Missing code (user denied consent), or a state mismatch (CSRF
        # attempt, expired attempt, or a stale tab replaying an old
        # callback URL) — all treated the same way: back to /login, no
        # session created.
        return _clear_oauth_cookies(error_redirect)

    link_user_id_raw = request.cookies.get(_LINK_INTENT_COOKIE_NAME)

    try:
        tokens = exchange_code_for_tokens(code)
        profile = fetch_userinfo(tokens["access_token"])
    except GoogleOAuthError:
        return _clear_oauth_cookies(error_redirect)

    google_id = profile["sub"]
    email = profile["email"]
    display_name = profile.get("name")

    # ── Explicit linking (S6-07 finding 1) — only when google_link above
    # is what actually started this flow. Never triggered by email
    # matching alone. ─────────────────────────────────────────────────
    if link_user_id_raw is not None:
        link_error_redirect = RedirectResponse(
            f"{_frontend_origin()}/settings?error=google_link_failed", status_code=HTTP_303_SEE_OTHER
        )

        try:
            link_user_id = UUID(link_user_id_raw)
        except ValueError:
            return _clear_oauth_cookies(link_error_redirect)

        linking_user = db.get(User, link_user_id)
        if linking_user is None:
            return _clear_oauth_cookies(link_error_redirect)

        already_linked_elsewhere = crud.get_user_by_google_id(db, google_id)
        if already_linked_elsewhere is not None and already_linked_elsewhere.id != linking_user.id:
            # This Google identity already belongs to a different account
            # — never repoint it, that would be the same takeover shape
            # in reverse (stealing a Google identity away from its real
            # owner into whatever account initiated this link request).
            return _clear_oauth_cookies(link_error_redirect)
        if linking_user.google_id is not None and linking_user.google_id != google_id:
            # The account initiating the link already has a different
            # Google identity attached — crud.link_google_id refuses to
            # overwrite it (by design), so surface that as a clean
            # failure here rather than a silent no-op.
            return _clear_oauth_cookies(link_error_redirect)

        crud.link_google_id(db, linking_user, google_id)

        success_redirect = RedirectResponse(
            f"{_frontend_origin()}/settings?linked=google", status_code=HTTP_303_SEE_OTHER
        )
        return _clear_oauth_cookies(success_redirect)

    # ── Plain sign-in ────────────────────────────────────────────────
    user = crud.get_user_by_google_id(db, google_id)
    if user is None:
        existing = crud.get_user_by_email(db, email)
        if existing is None:
            user = crud.create_user_from_google(db, google_id, email, display_name)
        else:
            # An account with this email already exists and has no
            # google_id linked yet. Before S6-07 finding 1, this branch
            # auto-linked — the real account-takeover path: an attacker
            # registers a password account under a victim's real,
            # unverified email, and the victim's own later Google
            # sign-in would silently attach to the attacker's row,
            # handing the attacker standing access to the victim's data.
            # Now: a conflict, not a silent link. The rightful owner logs
            # in with their password (S6-04) and connects Google
            # explicitly via /google/link above, from an authenticated
            # session — the only place linking is now allowed to happen.
            error_redirect = RedirectResponse(
                f"{_frontend_origin()}/login?error=google_email_already_registered",
                status_code=HTTP_303_SEE_OTHER,
            )
            return _clear_oauth_cookies(error_redirect)

    session_id = create_session(user.id)
    redirect = RedirectResponse(_frontend_origin(), status_code=HTTP_303_SEE_OTHER)
    set_session_cookie(redirect, session_id)
    return _clear_oauth_cookies(redirect)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        destroy_session(session_id)
    clear_session_cookie(response)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """S6-05 — the frontend's route guard calls this once on load to
    decide "does a valid session exist," rather than inferring it from
    whichever page-specific query happens to run first. get_current_user
    already does all the real work (401 on missing/expired/invalid
    session); this endpoint exists only to give the frontend one
    reliable, page-independent thing to ask.
    """
    return current_user


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
