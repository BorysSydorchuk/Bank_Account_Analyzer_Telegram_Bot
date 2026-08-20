"""The auth dependency every protected route uses (built S6-01, wired to
routes starting S6-05).
"""
import os

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from .session import SESSION_COOKIE_NAME, get_session

__all__ = ["get_current_user", "require_enable_banking_owner"]

_NOT_AUTHENTICATED = HTTPException(status_code=401, detail="Not authenticated. Please log in.")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolves the authenticated user from the session cookie. Raises 401
    if the cookie is missing, the session it names is expired/invalid, or
    the session's user_id no longer has a matching row (e.g. deleted
    between the session being issued and this request).
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise _NOT_AUTHENTICATED

    user_id = get_session(session_id)
    if user_id is None:
        raise _NOT_AUTHENTICATED

    user = db.get(User, user_id)
    if user is None:
        raise _NOT_AUTHENTICATED

    return user


def require_enable_banking_owner(current_user: User = Depends(get_current_user)) -> User:
    """S6-06 — the sync flow scopes DATA correctly per-user, but the single
    eb_session.json bank connection is still, physically, one account's
    connection (per-user bank session STORAGE is Sprint 7's job, which
    needs the public deployment context to do properly). Until then, this
    is the enforcement the ticket requires: only the account
    ENABLE_BANKING_OWNER_EMAIL names may trigger sync or touch the Enable
    Banking status/reauthorize/callback endpoints, rather than leaving the
    single shared connection open to every authenticated user. 403, not
    404 — this isn't a by-ID lookup hiding whether a resource exists
    (S5-01's IDOR pattern); it's a real, named permission boundary on a
    feature every authenticated user can see exists, just not use.
    """
    owner_email = os.getenv("ENABLE_BANKING_OWNER_EMAIL")
    if not owner_email or current_user.email != owner_email:
        raise HTTPException(
            status_code=403, detail="This Enable Banking connection isn't linked to your account."
        )
    return current_user
