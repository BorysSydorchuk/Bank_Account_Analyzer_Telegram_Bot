"""Google OAuth 2.0 authorization-code flow (S6-03) — sign-in only, no
Google API scopes beyond identity (`openid email profile`). Plain
`requests` calls against Google's documented endpoints rather than a
dedicated OAuth SDK: this app only ever needs three calls (build the
consent URL, exchange a code, read the profile), and `requests` is
already a dependency — a full SDK (`google-auth-oauthlib`) would pull in
more than this needs for three HTTP calls against fixed, stable Google
endpoints.
"""
import os
from urllib.parse import urlencode

import requests

__all__ = [
    "GoogleOAuthError",
    "get_client_id",
    "get_redirect_uri",
    "build_authorize_url",
    "exchange_code_for_tokens",
    "fetch_userinfo",
]

_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_SCOPES = "openid email profile"


class GoogleOAuthError(Exception):
    """Google rejected the code exchange, or returned a profile without a
    verified email — surfaced as a clean redirect-to-login-with-error, not
    a raw traceback."""


def _get_client_id() -> str:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise GoogleOAuthError(
            "GOOGLE_CLIENT_ID is not set. Create an OAuth 2.0 Client ID (Web application) "
            "in the Google Cloud Console and add it to .env."
        )
    return client_id


def _get_client_secret() -> str:
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_secret:
        raise GoogleOAuthError("GOOGLE_CLIENT_SECRET is not set. Add it to .env alongside GOOGLE_CLIENT_ID.")
    return client_secret


def get_client_id() -> str:
    return _get_client_id()


def get_redirect_uri() -> str:
    # Must exactly match a redirect URI registered on the OAuth client in
    # Google Cloud Console — Google rejects the request outright otherwise.
    return os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")


def build_authorize_url(state: str) -> str:
    """The URL to redirect the browser to for Google's consent screen.
    state is an opaque, unpredictable value the caller generated and will
    verify on the callback — CSRF protection for the whole flow (a
    forged callback with a stolen/replayed code is only exploitable if
    the attacker can also make the victim's browser carry a matching
    state, which they can't without also controlling the state cookie).
    """
    params = {
        "client_id": _get_client_id(),
        "redirect_uri": get_redirect_uri(),
        "response_type": "code",
        "scope": _SCOPES,
        "state": state,
        # Always show the account chooser rather than silently reusing
        # whichever Google account the browser is already signed into —
        # this app can have several Google accounts on one machine
        # (a household laptop, a shared dev machine), and "sign in with
        # Google" should always let the user pick.
        "prompt": "select_account",
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """Exchanges an authorization code for an access token. Raises
    GoogleOAuthError on any non-2xx response — a stale/already-used code
    is the most common real cause, per Google's own docs."""
    response = requests.post(
        _TOKEN_URL,
        data={
            "code": code,
            "client_id": _get_client_id(),
            "client_secret": _get_client_secret(),
            "redirect_uri": get_redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if not response.ok:
        raise GoogleOAuthError(
            "Google did not accept that authorization code — it may have expired or already been used."
        )
    return response.json()


def fetch_userinfo(access_token: str) -> dict:
    """The signed-in Google account's profile: sub (Google's stable user
    id), email, email_verified, name. Raises GoogleOAuthError if Google
    rejects the access token, or if the email isn't verified — an
    unverified email can't be trusted to actually belong to the person
    completing this flow, which matters most for the account-linking case
    (routers/user_auth.py): linking by email on an unverified address
    would let anyone claim an existing password account just by typing
    its email into a Google signup, without ever proving they own it.
    """
    response = requests.get(_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    if not response.ok:
        raise GoogleOAuthError("Could not fetch your Google profile — please try signing in again.")

    profile = response.json()
    if not profile.get("email_verified"):
        raise GoogleOAuthError(
            "Your Google account's email isn't verified with Google, so it can't be used to sign in here."
        )
    return profile
