"""S9-05: create the real Stripe Customer Portal configuration for Mymble
Pro's cancel/manage flow. One-off setup script, not called by the app at
runtime — the Stripe account has no portal configuration by default, and
`billing_portal.sessions.create` fails without one. Same test-mode guard
as scripts/create_stripe_products.py (S9-01). Safe to re-run; Stripe
creates a new configuration each time rather than updating in place — a
re-run just adds a second one and marks it default (harmless, delete the
old one manually in the dashboard if this happens).
Usage: python -m scripts.create_stripe_portal_configuration  (run from /backend)
"""
import os

import stripe
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    api_key = os.getenv("STRIPE_SECRET_KEY")
    if not api_key:
        raise SystemExit("STRIPE_SECRET_KEY not set in .env")
    if not (api_key.startswith("sk_test_") or api_key.startswith("rk_test_")):
        raise SystemExit(
            "Refusing to run: STRIPE_SECRET_KEY is not a test-mode key "
            "(expected sk_test_/rk_test_ prefix). This script must never touch live mode."
        )
    client = stripe.StripeClient(api_key)

    config = client.v1.billing_portal.configurations.create({
        "business_profile": {"headline": "Mymble Pro subscription management"},
        "features": {
            "customer_update": {"enabled": True, "allowed_updates": ["email"]},
            "invoice_history": {"enabled": True},
            "payment_method_update": {"enabled": True},
            "subscription_cancel": {"enabled": True},
        },
    })

    print(f"[stripe] Billing portal configuration created — id={config.id} is_default={config.is_default}")


if __name__ == "__main__":
    main()
