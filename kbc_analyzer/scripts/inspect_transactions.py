"""Fetch all transactions and display only the relevant fields."""
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.enablebanking.com"
SESSION_FILE = "eb_session.json"
DAYS_BACK = 30

KEEP_FIELDS = {
    "entry_reference",
    "transaction_amount",
    "creditor",
    "debtor_account",
    "debtor",
    "remittance_information",
}

app_id = os.getenv("ENABLEBANKING_APP_ID")
private_key = Path(os.getenv("ENABLEBANKING_PRIVATE_KEY_PATH")).read_text()

with open(SESSION_FILE) as f:
    session = json.load(f)


def make_token() -> str:
    now = int(time.time())
    return jwt.encode(
        {"iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": now, "exp": now + 3600},
        private_key,
        algorithm="RS256",
        headers={"typ": "JWT", "alg": "RS256", "kid": app_id},
    )


def fetch_all(account_uid: str) -> list[dict]:
    date_from = (date.today() - timedelta(days=DAYS_BACK)).isoformat()
    date_to = date.today().isoformat()
    all_txs = []
    continuation_key = None

    while True:
        params = {"date_from": date_from, "date_to": date_to}
        if continuation_key:
            params["continuation_key"] = continuation_key

        resp = requests.get(
            f"{BASE_URL}/accounts/{account_uid}/transactions",
            headers={"Authorization": f"Bearer {make_token()}", "Content-Type": "application/json"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        all_txs.extend(data.get("transactions", []))
        continuation_key = data.get("continuation_key")
        if not continuation_key:
            break

    return all_txs


def filter_fields(t: dict) -> dict:
    filtered = {k: t[k] for k in KEEP_FIELDS if k in t}
    filtered["_creditor_present"] = t.get("creditor") is not None
    return filtered


for account_uid in session["account_uids"]:
    txs = fetch_all(account_uid)
    print(f"Account {account_uid[:8]}… — {len(txs)} transactions\n")
    for t in txs:
        print(json.dumps(filter_fields(t), indent=2))
        print()
    print("=" * 60 + "\n")