"""Reusable Enable Banking service for the web app.

kbc_analyzer.enablebanking.EnableBankingClient already does the heavy lifting: it signs a
fresh short-lived JWT for every request (that's the "automatic" token refresh) and caches
the ~90-day OAuth session so repeated runs don't need re-authorization — as of S7-06, into
a per-user row in Postgres (app.eb_session_store.DatabaseSessionStore) rather than the
single shared eb_session.json file this class used to rely on implicitly. See that
module's docstring for why: a local file is neither durable across an ECS redeploy nor
visible to the separate worker task that runs sync.

The one thing it can't do inside an API request handler is the *interactive* re-auth flow
(print a URL, block on `input()` for the pasted redirect) — that only makes sense in a
terminal. So this class stays read-only with respect to authorization: if there's no valid
cached session, it raises a clear error instead of hanging the request. Re-authorizing still
happens via the web reconnect flow (POST /reauthorize + GET /callback) or, for the
terminal/bot, `python -m kbc_analyzer.main`.
"""
import os
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from kbc_analyzer.enablebanking import EnableBankingClient, EnableBankingError

from .eb_session_store import DatabaseSessionStore

__all__ = ["EnableBankingService", "EnableBankingAuthError", "EnableBankingError"]


class EnableBankingAuthError(Exception):
    """No valid cached bank session is available for the API to use."""


class EnableBankingService:
    def __init__(self, db: Session, user_id: UUID, institution: str) -> None:
        # S7-06: one EnableBankingClient per request, scoped to whichever
        # user's session is being read or written — replaces the old
        # no-argument constructor that always pointed at the single shared
        # eb_session.json file. Every caller (routers/auth.py,
        # tasks/analysis.py) now passes the authenticated/owning user_id
        # explicitly, the same pattern S6-06 already established for every
        # other per-user query in this codebase.
        #
        # S8-01: also scoped to institution — one service instance now
        # represents one (user, bank) connection, following
        # enable_banking_sessions' composite-key migration. Callers that
        # need to know which banks a user has connected at all (the status
        # endpoint, sync) use connected_institutions() below rather than
        # this constructor.
        self.institution = institution
        self._client = EnableBankingClient(
            app_id=os.getenv("ENABLEBANKING_APP_ID"),
            private_key_path=os.getenv("ENABLEBANKING_PRIVATE_KEY_PATH"),
            session_store=DatabaseSessionStore(db, user_id, institution),
        )

    @staticmethod
    def connected_institutions(db: Session, user_id: UUID) -> list[str]:
        """Every institution this user has ever connected — see
        DatabaseSessionStore.connected_institutions. A thin passthrough so
        callers only need to import EnableBankingService, not the storage
        layer underneath it.
        """
        return DatabaseSessionStore.connected_institutions(db, user_id)

    def get_account_uids(self) -> list[str]:
        if not self._client.session_valid():
            # S7-07: used to tell the caller to run `python -m
            # kbc_analyzer.main` — impossible advice for a web user, and
            # the one place the web app's own code still pointed someone
            # at a terminal command instead of the Settings page.
            raise EnableBankingAuthError(
                "No active bank connection (or it has expired). Connect your "
                "bank in Settings, then try again."
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
        """Report whether a usable session exists for this institution, and when it expires.

        Deliberately doesn't use session_valid()'s 1-day safety buffer — that buffer
        exists to stop *sync* from using a nearly-dead session, whereas this reports
        the real expiry so the frontend can decide its own warning threshold.

        S7-07: "never connected" and "connected, then lapsed" used to both
        report as "expired" — correct for sync (either way, sync can't
        run), wrong for the UI, which needs to say "Connect your bank" to
        a first-time user and "Reconnect" to someone whose session
        actually expired. `get_session_info() is None` is the only signal
        that distinguishes them — session_store.load() returns None only
        when no row has ever been written for this user.
        """
        info = self._client.get_session_info()
        if info is None:
            return {"status": "not_connected", "expires_at": None}
        valid_until = info.get("valid_until")
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
        return self._client.start_auth(state, institution=self.institution)

    def complete_reauthorization(self, code: str) -> dict:
        """Exchange the authorization code (pasted back from the redirect URL) for a new
        session, persist it, and return the resulting status — active, with the new expiry.
        """
        self._client.complete_auth_with_code(code)
        return self.get_session_status()
