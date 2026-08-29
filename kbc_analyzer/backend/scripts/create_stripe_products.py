"""S9-01: create the real Stripe test-mode Product + Price for Mymble Pro.
One-off setup script, not called by the app at runtime — the resulting
price ID gets pasted into config once created. Safe to re-run; Stripe
does not dedupe products/prices by name, so re-running creates duplicates
in the test-mode dashboard (harmless there, just delete extras manually).
Usage: python -m scripts.create_stripe_products  (run from /backend)
"""
import os

import stripe
from dotenv import load_dotenv

load_dotenv()

PRODUCT_NAME = "Mymble Pro"
PRICE_EUR_CENTS = 999  # €9.99/month, confirmed by Borys for S9-01


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

    product = client.products.create({
        "name": PRODUCT_NAME,
        "description": "Mymble paid tier — higher daily usage limits than the free tier.",
    })
    price = client.prices.create({
        "product": product.id,
        "unit_amount": PRICE_EUR_CENTS,
        "currency": "eur",
        "recurring": {"interval": "month"},
    })

    print(f"[stripe] Product created — id={product.id} name={product.name!r}")
    print(f"[stripe] Price created   — id={price.id} amount={price.unit_amount / 100:.2f} {price.currency.upper()}/{price.recurring['interval']}")


if __name__ == "__main__":
    main()
