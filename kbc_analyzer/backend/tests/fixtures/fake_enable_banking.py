"""A fake Enable Banking client (TESTER.md prime directive 3: no live bank
calls, ever) mocked at the same boundary app/eb_service.py imports —
`EnableBankingService.__init__` constructs a real `EnableBankingClient`
directly (there's no dependency-injection seam), so the mock replaces the
class reference inside app.eb_service's own namespace, not the original
module's. Implements only the methods eb_service.py actually calls.
"""
from datetime import date, datetime, timedelta, timezone

import pytest


class FakeEnableBankingClient:
    def __init__(self, app_id: str = "fake", private_key_path: str = "unused", **kwargs):
        self._session_valid = True
        self._valid_until = datetime.now(timezone.utc) + timedelta(days=90)
        self._account_uids = ["fake-account-uid-1"]
        self._transactions: list[dict] = []
        self.started_auth = False
        self.completed_codes: list[str] = []

    def session_valid(self) -> bool:
        return self._session_valid

    def get_cached_uids(self) -> list[str]:
        return self._account_uids

    def get_session_info(self) -> dict | None:
        if not self._session_valid:
            return None
        return {"valid_until": self._valid_until.isoformat()}

    def start_auth(self) -> str:
        self.started_auth = True
        return "https://fake-eb.example/authorize?state=fake"

    def complete_auth_with_code(self, code: str) -> list[str]:
        self.completed_codes.append(code)
        self._session_valid = True
        self._valid_until = datetime.now(timezone.utc) + timedelta(days=90)
        return self._account_uids

    def fetch_transactions(self, account_uid: str, date_from: date) -> list[dict]:
        return [t for t in self._transactions if t["date"] >= date_from.isoformat()]

    # Test-only helpers, not part of the real client's interface.
    def set_transactions(self, transactions: list[dict]) -> None:
        self._transactions = transactions

    def expire_session(self) -> None:
        self._session_valid = False


@pytest.fixture
def mock_enable_banking_client(monkeypatch):
    """Patches app.eb_service's imported reference to EnableBankingClient so
    any EnableBankingService() constructed during the test gets a
    FakeEnableBankingClient instead. Returns the fake instance."""
    fake = FakeEnableBankingClient()
    monkeypatch.setattr("app.eb_service.EnableBankingClient", lambda **kwargs: fake)
    return fake
