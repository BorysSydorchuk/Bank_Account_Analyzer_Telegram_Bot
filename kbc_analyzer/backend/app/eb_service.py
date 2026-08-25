"""Reusable Enable Banking service for the web app.

kbc_analyzer.enablebanking.EnableBankingClient already does the heavy lifting: it signs a
fresh short-lived JWT for every request (that's the "automatic" token refresh) and caches
the ~90-day OAuth session to eb_session.json so repeated runs don't need re-authorization.

The one thing it can't do inside an API request handler is the *interactive* re-auth flow
(print a URL, block on `input()` for the pasted redirect) — that only makes sense in a
terminal. So this class stays read-only with respect to authorization: if there's no valid
cached session, it raises a clear error instead of hanging the request. Re-authorizing still
happens via `python -m kbc_analyzer.main` until a later ticket adds a web-based auth flow.
"""
import os
from datetime import date, datetime

from kbc_analyzer.enablebanking import EnableBankingClient, EnableBankingError

__all__ = ["EnableBankingService", "EnableBankingAuthError", "EnableBankingError"]


class EnableBankingAuthError(Exception):
    """No valid cached KBC session is available for the API to use."""


class EnableBankingService:
    def __init__(self) -> None:
        self._client = EnableBankingClient(
            app_id=os.getenv("ENABLEBANKING_APP_ID"),
            private_key_path=os.getenv("ENABLEBANKING_PRIVATE_KEY_PATH"),
        )

    def get_account_uids(self) -> list[str]:
        if not self._client.session_valid():
            raise EnableBankingAuthError(
                "No active KBC session (or it has expired). Run "
                "`python -m kbc_analyzer.main` once to authorize access, then retry."
            )
        return self._client.get_cached_uids()

    def fetch_transactions(self, account_uid: str, date_from: date, date_to: date) -> list[dict]:
        """Fetch and narrow the result to [date_from, date_to].

        The underlying client always fetches from date_from through today (it has no
        date_to parameter), so we filter client-side afterwards — the same pattern
        kbc_analyzer.bot already uses for its /compare flow.
        """
        txs = self._client.fetch_transactions(account_uid, date_from)
        return [t for t in txs if date_from.isoformat() <= t["date"] <= date_to.isoformat()]

    # ── Web re-consent flow (S2-02) ─────────────────────────────────────────
    # The interactive terminal flow (print URL, block on input()) only makes sense in a
    # console, so these three methods are the web equivalent: report status, hand back
    # an authorization URL for the user to open themselves, and complete the exchange
    # once they paste back the code — no step here ever blocks waiting on user input.

    def get_session_status(self) -> dict:
        """Report whether a usable KBC session exists, and when it expires.

        Deliberately doesn't use session_valid()'s 1-day safety buffer — that buffer
        exists to stop *sync* from using a nearly-dead session, whereas this reports
        the real expiry so the frontend can decide its own warning threshold.
        """
        info = self._client.get_session_info()
        valid_until = info.get("valid_until") if info else None
        if not valid_until or datetime.fromisoformat(valid_until) <= datetime.now():
            return {"status": "expired", "expires_at": None}
        return {"status": "active", "expires_at": valid_until}

    def get_reauthorize_url(self, state: str | None = None) -> str:
        """Start a new Enable Banking authorization session and return the URL the user
        must open in their browser. Does not touch the cached session — nothing is
        considered re-authorized until complete_reauthorization() runs successfully.

        state: passed straight through to the Enable Banking request (S7-04) so the
        caller can later verify the callback's state matches what it set here.
        """
        return self._client.start_auth(state)

    def complete_reauthorization(self, code: str) -> dict:
        """Exchange the authorization code (pasted back from the redirect URL) for a new
        session, persist it, and return the resulting status — active, with the new expiry.
        """
        self._client.complete_auth_with_code(code)
        return self.get_session_status()
