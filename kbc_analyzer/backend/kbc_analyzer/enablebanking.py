"""Enable Banking API client — handles PSD2 OAuth authorization and transaction fetching.

Enable Banking is a third-party aggregator that connects to KBC Belgium (and other European
banks) via the PSD2 Open Banking regulation. It lets us read real account transactions without
screen scraping. Every API request is authenticated with a short-lived RSA-signed JWT token.
"""
import json
import os
import re
import secrets
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse  # used to extract the OAuth code from the redirect URL

import jwt  # PyJWT — creates RS256-signed tokens
import requests
from rich.console import Console

console = Console()

# Base URL for all Enable Banking REST calls
BASE_URL = "https://api.enablebanking.com"

# Local file where we cache the active session (account UIDs + expiry date)
SESSION_FILE = "eb_session.json"

# Where Enable Banking redirects after login/consent. S3-07 Item 2 replaced
# the old copy-paste-the-URL flow with a local catcher server (see
# backend/app/eb_callback_server.py and backend/app/tasks/auth.py) that
# listens on this exact address. An earlier http:// version of this URI was
# rejected LIVE by Enable Banking's /auth endpoint ("400 Redirect URI not
# allowed") because the portal only accepts https:// scheme redirect URIs.
# The catcher server now serves HTTPS via an mkcert-generated localhost
# certificate, and https://localhost:3001/callback has been registered for
# this app_id in the Enable Banking developer portal — this is the live value.
REDIRECT_URL = "https://localhost:3001/callback"


class EnableBankingError(Exception):
    """Raised for any Enable Banking API or configuration error."""
    pass


class EnableBankingClient:
    """Wraps the Enable Banking API: JWT auth, OAuth session flow, and transaction fetching."""

    def __init__(self, app_id: str, private_key_path: str):
        # app_id identifies our application in the Enable Banking portal
        self.app_id = app_id
        # Path to the RSA private key PEM file downloaded from the Enable Banking portal
        self.private_key_path = private_key_path
        # Cache the loaded key text so we only read the file once
        self._private_key: str | None = None

    @property
    def private_key(self) -> str:
        """Lazily load and cache the RSA private key from disk."""
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
        """Create a short-lived RS256 JWT that authenticates this request to Enable Banking.

        The token is valid for 1 hour. Enable Banking verifies the signature using the
        public key registered in the portal, and uses `kid` (the app_id) to look it up.
        """
        now = int(time.time())  # current Unix timestamp
        return jwt.encode(
            payload={
                "iss": "enablebanking.com",      # issuer — required constant
                "aud": "api.enablebanking.com",  # audience — required constant
                "iat": now,                       # issued-at timestamp
                "exp": now + 3600,                # expiry: 1 hour from now
            },
            key=self.private_key,
            algorithm="RS256",                   # RSA with SHA-256 signature
            headers={
                "typ": "JWT",
                "alg": "RS256",
                "kid": self.app_id,              # tells the server which public key to use
            },
        )

    def _headers(self) -> dict:
        """Build the HTTP headers required for every Enable Banking API call."""
        return {
            "Authorization": f"Bearer {self._make_jwt()}",  # fresh JWT per request
            "Content-Type": "application/json",
        }

    def _get(self, path: str, **params) -> dict:
        """Send a GET request to the Enable Banking API and return the parsed JSON body."""
        resp = requests.get(
            f"{BASE_URL}{path}",
            headers=self._headers(),
            # Filter out None values so optional query parameters aren't sent as "None"
            params={k: v for k, v in params.items() if v is not None},
            timeout=30,
        )
        if not resp.ok:
            raise EnableBankingError(f"GET {path} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        """Send a POST request to the Enable Banking API and return the parsed JSON body."""
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
        """Look up KBC Belgium in the list of supported banks (ASPSPs = Account Servicing Payment
        Service Providers — the official PSD2 term for banks).
        """
        # Fetch all Belgian banks registered on Enable Banking
        data = self._get("/aspsps", country="BE")
        items = data if isinstance(data, list) else data.get("aspsps", [])

        # Find the first entry whose name contains "KBC" (case-insensitive)
        kbc = next((a for a in items if "KBC" in a.get("name", "").upper()), None)
        if not kbc:
            names = [a.get("name") for a in items[:10]]
            raise EnableBankingError(f"KBC not found in Belgian ASPSPs. Available: {names}")
        return kbc

    # ── Session helpers ────────────────────────────────────────────────────────

    def session_valid(self) -> bool:
        """Return True if a cached OAuth session exists and won't expire within a day.

        The session file stores the expiry timestamp set when we first authorized.
        Sessions last ~90 days, after which the user must re-authorize via KBC's website.
        """
        if not os.path.exists(SESSION_FILE):
            return False  # never authorized before
        with open(SESSION_FILE) as f:
            data = json.load(f)
        # Add a 1-day buffer so we don't try to use a nearly-expired session
        return datetime.fromisoformat(data["valid_until"]) > datetime.now() + timedelta(days=1)

    def get_cached_uids(self) -> list[str]:
        """Return the list of account UIDs from the cached session file.

        Each UID is a unique identifier for one bank account (e.g. a current or savings account).
        Call only after confirming session_valid() == True.
        """
        with open(SESSION_FILE) as f:
            return json.load(f)["account_uids"]

    def get_session_info(self) -> dict | None:
        """Return the raw cached session dict (session_id, account_uids, valid_until),
        or None if no session has ever been created. Used to report session status to
        the web UI — unlike session_valid(), this doesn't apply the 1-day safety buffer,
        since the UI wants the real expiry date, not a buffered "is it safe to use" answer.
        """
        if not os.path.exists(SESSION_FILE):
            return None
        with open(SESSION_FILE) as f:
            return json.load(f)

    # ── Non-interactive auth (used by the Telegram bot) ────────────────────────

    def start_auth(self) -> str:
        """Step 1 of the OAuth flow: request a new authorization session and return the URL
        the user must open in their browser to grant us access to their KBC account.

        The Enable Banking OAuth flow:
          1. We POST /auth → get back a URL
          2. User opens URL, logs in to KBC, grants consent
          3. KBC redirects to REDIRECT_URL?code=...
          4. Something completes the exchange from that code — the web flow's local
             catcher server does this automatically (S3-07 Item 2); the terminal flow
             below still asks the user to paste the URL by hand.
          5. We call complete_auth() to exchange the code for a session
        """
        kbc = self._find_kbc_aspsp()

        # Request 90 days of access starting from now
        valid_until = (datetime.utcnow() + timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")

        auth = self._post("/auth", {
            "access": {
                "valid_until": valid_until,
                "balances": True,       # permission to read account balances
                "transactions": True,   # permission to read transactions
            },
            "aspsp": {
                "name": kbc["name"],
                "country": kbc.get("country", "BE"),
            },
            # Random state string to prevent CSRF — not checked by us but required by the spec
            "state": secrets.token_urlsafe(16),
            "redirect_url": REDIRECT_URL,
            "psu_type": "personal",     # PSU = Payment Service User (the account owner)
        })
        return auth["url"]  # the KBC login URL the user needs to open

    def complete_auth(self, redirect_url: str) -> list[str]:
        """Step 2 of the OAuth flow: extract the authorization code from the redirect URL,
        exchange it for a session, cache the session locally, and return account UIDs.

        Args:
            redirect_url: The full URL the user copied from their browser address bar,
                          e.g. https://localhost/callback?code=abc123&state=xyz
        """
        # Parse the URL and extract query parameters
        parsed = urlparse(redirect_url.strip())
        params = parse_qs(parsed.query)  # {'code': ['abc123'], 'state': ['xyz']}

        if "code" not in params:
            raise EnableBankingError(
                "No 'code' found in the pasted URL. "
                "Make sure you copied the full address bar URL after being redirected."
            )

        return self.complete_auth_with_code(params["code"][0])

    def complete_auth_with_code(self, code: str) -> list[str]:
        """The back half of complete_auth(), starting from an already-extracted code.

        Split out so the web callback endpoint (S2-02) — which receives {code, state}
        as JSON, not a full redirect URL — can reuse the exact same session-exchange
        and caching logic the terminal/bot flows already rely on.
        """
        # Exchange the authorization code for a session object containing account UIDs
        session = self._post("/sessions", {"code": code})

        # Extract UIDs for all linked accounts (could be current + savings account)
        account_uids = [acc["uid"] for acc in session.get("accounts", [])]

        # Persist the session to disk so we don't need to re-authorize for ~90 days
        with open(SESSION_FILE, "w") as f:
            json.dump({
                "session_id": session.get("session_id", ""),
                "account_uids": account_uids,
                # Store when this session expires (89 days to be safe)
                "valid_until": (datetime.now() + timedelta(days=89)).isoformat(),
            }, f)

        return account_uids

    # ── Interactive terminal flow ──────────────────────────────────────────────

    def ensure_session(self) -> list[str]:
        """Return account UIDs for the active session.

        If the session is still valid, returns cached UIDs immediately.
        Otherwise, runs the interactive terminal auth flow (prints URL, waits for paste).
        Used by main.py (terminal entry point); the bot uses start_auth/complete_auth instead.
        """
        if self.session_valid():
            console.print("[green]✓ KBC session active[/green]")
            return self.get_cached_uids()
        console.print("[yellow]Session expired — re-authorization required[/yellow]")
        return self._create_session()

    def _create_session(self) -> list[str]:
        """Interactive terminal auth: print the authorization URL and prompt the user to paste
        back the redirect URL. Completes the OAuth flow and returns account UIDs.
        """
        kbc = self._find_kbc_aspsp()
        console.print(f"[cyan]Connecting to: {kbc['name']}[/cyan]")

        url = self.start_auth()  # get the URL to open in the browser

        console.print(
            "\n[bold yellow]Action required:[/bold yellow] "
            "Open this URL in your browser to authorize KBC access:\n"
        )
        console.print(f"  [link]{url}[/link]\n")
        console.print(
            "Log in with your KBC credentials. You will be redirected to "
            f"[bold]{REDIRECT_URL}?code=...[/bold]\n"
            "The browser will show a 'can't connect' error unless something is listening "
            "on that port — that is expected here.\n"
            "Copy the [bold]full URL[/bold] from your browser's address bar and paste it below."
        )
        redirect_url = input("\nPaste the full redirect URL: ").strip()

        account_uids = self.complete_auth(redirect_url)
        console.print(f"[green]✓ KBC session created — {len(account_uids)} account(s) linked[/green]")
        return account_uids

    # ── Transaction fetching ───────────────────────────────────────────────────

    def fetch_transactions(self, account_uid: str, date_from: date) -> list[dict]:
        """Fetch all transactions for one account starting from date_from until today.

        Enable Banking returns at most ~100 transactions per page. If there are more,
        the response includes a continuation_key; we loop until there is none.
        Each transaction is normalized to a simple {id, date, amount, description} dict.
        """
        all_txs: list[dict] = []
        continuation_key: str | None = None  # None on the first request

        while True:
            data = self._get(
                f"/accounts/{account_uid}/transactions",
                date_from=date_from.isoformat(),
                date_to=date.today().isoformat(),
                continuation_key=continuation_key,  # None is filtered out in _get()
            )

            # Normalize and collect each transaction on this page
            for t in data.get("transactions", []):
                all_txs.append(self._normalize(t))

            # If there are more pages, the API returns a continuation_key we must pass next time
            continuation_key = data.get("continuation_key")
            if not continuation_key:
                break  # all pages have been fetched

        return all_txs

    @staticmethod
    def _extract_merchant(remittance: str) -> str:
        """Extract a clean merchant name from a card-payment remittance string.

        Card payments arrive with a remittance like:
            "DELHAIZE BRUSSEL  BE1234 BRUSSELS Payment with Maestro..."
        We strip everything from the first postal-code pattern (two uppercase letters +
        four digits) onwards, leaving just the merchant name.
        """
        # Regex: whitespace + two uppercase letters + four digits + everything after
        cleaned = re.sub(r'\s+[A-Z]{2}\d{4}.*$', '', remittance).strip()
        # Fall back to the first 50 characters if the regex stripped everything
        return cleaned or remittance[:50]

    @staticmethod
    def _normalize(t: dict) -> dict:
        """Convert a raw Enable Banking transaction object into a flat, typed dict.

        Enable Banking returns amounts as always-positive numbers. The direction of money
        flow (spent vs. received) is encoded in credit_debit_indicator:
          - DBIT (debit)  = money leaving the account → we make the amount negative
          - CRDT (credit) = money arriving            → amount stays positive

        For the description we use different fields depending on direction:
          - Debits (spending): use the creditor's name (who we paid), or extract the
            merchant name from the remittance string (card payments)
          - Credits (income): use the debtor's name (who paid us)
        """
        amount_data = t.get("transaction_amount", {})
        creditor = t.get("creditor") or {}          # who received the money (for debits)
        remittance = t.get("remittance_information") or []  # free-text payment references
        indicator = t.get("credit_debit_indicator", "DBIT")  # "DBIT" or "CRDT"

        # Enable Banking always gives a positive amount; apply sign based on direction
        amount = float(amount_data.get("amount", 0))
        if indicator == "DBIT":
            amount = -amount  # spending = negative

        # Build a human-readable description
        if indicator == "DBIT":
            if creditor.get("name"):
                # Bank transfer to a named recipient (e.g. a utility company or person)
                description = creditor["name"]
            elif remittance:
                # Card payment — remittance contains merchant name + location; extract just the name
                description = EnableBankingClient._extract_merchant(remittance[0])
            else:
                description = "Unknown"
        else:
            # Credit: show who sent us the money
            debtor = t.get("debtor") or {}
            description = debtor.get("name") or (remittance[0] if remittance else "Unknown")

        return {
            "id": t.get("entry_reference", ""),          # unique transaction reference from the bank
            "date": t.get("booking_date") or t.get("value_date", ""),  # prefer booking date
            "amount": amount,                             # signed float in EUR
            "description": description,                  # merchant / sender name
        }
