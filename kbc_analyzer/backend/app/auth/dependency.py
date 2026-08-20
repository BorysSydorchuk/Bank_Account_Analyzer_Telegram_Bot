"""The auth dependency every protected route will use, starting S6-05
(this ticket only builds it — nothing is wired to it yet).
"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from .session import SESSION_COOKIE_NAME, get_session

__all__ = ["get_current_user"]

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
