"""Shared Stripe API client builder for app runtime code (S9-03).

Same test-mode guard as scripts/create_stripe_products.py (S9-01) — not
imported from there since that script is one-off setup tooling, not part
of the running app, and this module is the first *runtime* caller to need
the same construction.
"""
import os

import stripe

__all__ = ["get_stripe_client"]


def get_stripe_client() -> stripe.StripeClient:
    """A Stripe client bound to STRIPE_SECRET_KEY. Raises if that key isn't
    a test-mode key — this app must never touch live mode until Borys
    deliberately activates it (see ARCHITECTURE.md's Billing section).
    """
    api_key = os.environ["STRIPE_SECRET_KEY"]
    if not (api_key.startswith("sk_test_") or api_key.startswith("rk_test_")):
        raise RuntimeError(
            "Refusing to build a Stripe client: STRIPE_SECRET_KEY is not a test-mode key "
            "(expected sk_test_/rk_test_ prefix). This app must never touch live mode."
        )
    return stripe.StripeClient(api_key)
