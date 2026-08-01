"""Run this once to inspect raw Enable Banking transaction fields.
Usage: python scripts/debug_fetch.py  (run from project root)
"""
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from pathlib import Path

import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.enablebanking.com"
SESSION_FILE = "eb_session.json"

app_id = os.getenv("ENABLEBANKING_APP_ID")
private_key = Path(os.getenv("ENABLEBANKING_PRIVATE_KEY_PATH")).read_text()

with open(SESSION_FILE) as f:
    session = json.load(f)

account_uids = session["account_uids"]

now = int(time.time())
token = jwt.encode(
    {"iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": now, "exp": now + 3600},
    private_key,
    algorithm="RS256",
    headers={"typ": "JWT", "alg": "RS256", "kid": app_id},
)

date_from = (date.today() - timedelta(days=30)).isoformat()

for account_uid in account_uids:
    resp = requests.get(
        f"{BASE_URL}/accounts/{account_uid}/transactions",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params={"date_from": date_from, "date_to": date.today().isoformat()},
        timeout=30,
    )

    data = resp.json()
    transactions = data.get("transactions", [])
    print(f"Account {account_uid[:8]}… — {len(transactions)} transactions")
    print(f"\n--- First 5 raw transactions ---\n")
    for t in transactions[:5]:
        print(json.dumps(t, indent=2))
        print()
    print("=" * 60 + "\n")