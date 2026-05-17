import json
import os
import re
import secrets
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jwt  # PyJWT
import requests
from rich.console import Console

console = Console()

BASE_URL = "https://api.enablebanking.com"
SESSION_FILE = "eb_session.json"


class EnableBankingError(Exception):
    pass


class EnableBankingClient:
    def __init__(self, app_id: str, private_key_path: str):
        self.app_id = app_id
        self.private_key_path = private_key_path
        self._private_key: str | None = None

    @property
    def private_key(self) -> str:
        if self._private_key is None:
            path = Path(self.private_key_path)
            if not path.exists():
                raise EnableBankingError(
                    f"Private key file not found: {self.private_key_path}\n"
                    "Download it from the Enable Banking portal and place it in the project directory."
                )
            self._private_key = path.read_text()
        return self._private_key

    def _make_jwt(self) -> str:
        now = int(time.time())
        return jwt.encode(
            payload={
                "iss": "enablebanking.com",
                "aud": "api.enablebanking.com",
                "iat": now,
                "exp": now + 3600,
            },
            key=self.private_key,
            algorithm="RS256",
            headers={
                "typ": "JWT",
                "alg": "RS256",
                "kid": self.app_id,
            },
        )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._make_jwt()}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, **params) -> dict:
        resp = requests.get(
            f"{BASE_URL}{path}",
            headers=self._headers(),
            params={k: v for k, v in params.items() if v is not None},
            timeout=30,
        )
        if not resp.ok:
            raise EnableBankingError(f"GET {path} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        resp = requests.post(
            f"{BASE_URL}{path}",
            headers=self._headers(),
            json=body,
            timeout=30,
        )
        if not resp.ok:
            raise EnableBankingError(f"POST {path} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def _find_kbc_aspsp(self) -> dict:
        data = self._get("/aspsps", country="BE")
        items = data if isinstance(data, list) else data.get("aspsps", [])
        kbc = next((a for a in items if "KBC" in a.get("name", "").upper()), None)
        if not kbc:
            names = [a.get("name") for a in items[:10]]
            raise EnableBankingError(f"KBC not found in Belgian ASPSPs. Available: {names}")
        return kbc

    # --- Session helpers ---

    def session_valid(self) -> bool:
        """Returns True if a cached session exists and won't expire within a day."""
        if not os.path.exists(SESSION_FILE):
            return False
        with open(SESSION_FILE) as f:
            data = json.load(f)
        return datetime.fromisoformat(data["valid_until"]) > datetime.now() + timedelta(days=1)

    def get_cached_uids(self) -> list[str]:
        """Return cached account UIDs without any API calls. Call only after session_valid()."""
        with open(SESSION_FILE) as f:
            return json.load(f)["account_uids"]

    # --- Non-interactive auth (used by Telegram bot) ---

    def start_auth(self) -> str:
        """Step 1: create an auth session and return the URL the user must open."""
        kbc = self._find_kbc_aspsp()
        valid_until = (datetime.utcnow() + timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
        auth = self._post("/auth", {
            "access": {
                "valid_until": valid_until,
                "balances": True,
                "transactions": True,
            },
            "aspsp": {
                "name": kbc["name"],
                "country": kbc.get("country", "BE"),
            },
            "state": secrets.token_urlsafe(16),
            "redirect_url": "https://localhost/callback",
            "psu_type": "personal",
        })
        return auth["url"]

    def complete_auth(self, redirect_url: str) -> list[str]:
        """Step 2: extract code from redirect URL, create session, cache it, return UIDs."""
        parsed = urlparse(redirect_url.strip())
        params = parse_qs(parsed.query)
        if "code" not in params:
            raise EnableBankingError(
                "No 'code' found in the pasted URL. "
                "Make sure you copied the full address bar URL after being redirected."
            )

        session = self._post("/sessions", {"code": params["code"][0]})
        account_uids = [acc["uid"] for acc in session.get("accounts", [])]

        with open(SESSION_FILE, "w") as f:
            json.dump({
                "session_id": session.get("session_id", ""),
                "account_uids": account_uids,
                "valid_until": (datetime.now() + timedelta(days=89)).isoformat(),
            }, f)

        return account_uids

    # --- Interactive terminal flow ---

    def ensure_session(self) -> list[str]:
        """Return cached account UIDs, running the interactive auth flow if needed."""
        if self.session_valid():
            console.print("[green]✓ KBC session active[/green]")
            return self.get_cached_uids()
        console.print("[yellow]Session expired — re-authorization required[/yellow]")
        return self._create_session()

    def _create_session(self) -> list[str]:
        """Interactive terminal auth: print URL, prompt for redirect, complete auth."""
        kbc = self._find_kbc_aspsp()
        console.print(f"[cyan]Connecting to: {kbc['name']}[/cyan]")

        url = self.start_auth()

        console.print(
            "\n[bold yellow]Action required:[/bold yellow] "
            "Open this URL in your browser to authorize KBC access:\n"
        )
        console.print(f"  [link]{url}[/link]\n")
        console.print(
            "Log in with your KBC credentials. You will be redirected to "
            "[bold]https://localhost/callback?code=...[/bold]\n"
            "The browser will show a 'can't connect' error — that is expected.\n"
            "Copy the [bold]full URL[/bold] from your browser's address bar and paste it below."
        )
        redirect_url = input("\nPaste the full redirect URL: ").strip()

        account_uids = self.complete_auth(redirect_url)
        console.print(f"[green]✓ KBC session created — {len(account_uids)} account(s) linked[/green]")
        return account_uids

    def fetch_transactions(self, account_uid: str, date_from: date) -> list[dict]:
        """Fetch all transactions for the given account, handling pagination."""
        all_txs: list[dict] = []
        continuation_key: str | None = None

        while True:
            data = self._get(
                f"/accounts/{account_uid}/transactions",
                date_from=date_from.isoformat(),
                date_to=date.today().isoformat(),
                continuation_key=continuation_key,
            )
            for t in data.get("transactions", []):
                all_txs.append(self._normalize(t))

            continuation_key = data.get("continuation_key")
            if not continuation_key:
                break

        return all_txs

    @staticmethod
    def _extract_merchant(remittance: str) -> str:
        # Card payment format: "MERCHANT CITY CC1234 CITY Payment with ..."
        cleaned = re.sub(r'\s+[A-Z]{2}\d{4}.*$', '', remittance).strip()
        return cleaned or remittance[:50]

    @staticmethod
    def _normalize(t: dict) -> dict:
        amount_data = t.get("transaction_amount", {})
        creditor = t.get("creditor") or {}
        remittance = t.get("remittance_information") or []
        indicator = t.get("credit_debit_indicator", "DBIT")

        amount = float(amount_data.get("amount", 0))
        if indicator == "DBIT":
            amount = -amount

        if indicator == "DBIT":
            if creditor.get("name"):
                description = creditor["name"]
            elif remittance:
                description = EnableBankingClient._extract_merchant(remittance[0])
            else:
                description = "Unknown"
        else:
            debtor = t.get("debtor") or {}
            description = debtor.get("name") or (remittance[0] if remittance else "Unknown")

        return {
            "id": t.get("entry_reference", ""),
            "date": t.get("booking_date") or t.get("value_date", ""),
            "amount": amount,
            "description": description,
        }
