"""A fake Stripe client (S9-03) — TESTER.md prime directive 3: no live
external calls, ever. Patches app.stripe_client.get_stripe_client's return
value (the one indirection point app/routers/billing.py calls for every
real Stripe API call), not the `stripe` package itself — `stripe.Webhook
.construct_event` stays real and unpatched everywhere, since signature
verification is pure local HMAC/JSON, not a network call, and exercising
the real verification code is the whole point of the webhook tests.
"""
from types import SimpleNamespace

import pytest


class _FakeStripeObject:
    """Minimal stand-in for the real SDK's StripeObject. Deliberately NOT a
    dict subclass — the real StripeObject supports attribute access
    (`.status`) and item access (`obj["status"]`) but raises on `.get(...)`
    ("a StripeObject is not a dict"). A dict-based fake would have hidden
    the real bug this fixture caught during development: app/routers
    /billing.py originally called `.get(...)` on real event objects and
    passed tests purely because this fake was too permissive.
    """

    def __init__(self, **fields):
        self._fields = fields

    def __getattr__(self, name):
        try:
            return self._fields[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __getitem__(self, name):
        return self._fields[name]


class _FakeCheckoutSessionsAPI:
    def __init__(self, fake_client: "FakeStripeClient"):
        self._fake_client = fake_client

    def create(self, params: dict):
        self._fake_client.created_checkout_params.append(params)
        return SimpleNamespace(url="https://checkout.stripe.com/test_fake_session")


class _FakeSubscriptionsAPI:
    def __init__(self, fake_client: "FakeStripeClient"):
        self._fake_client = fake_client

    def retrieve(self, subscription_id: str):
        return self._fake_client.subscription_objects[subscription_id]


class _FakePortalSessionsAPI:
    def __init__(self, fake_client: "FakeStripeClient"):
        self._fake_client = fake_client

    def create(self, params: dict):
        self._fake_client.created_portal_params.append(params)
        return SimpleNamespace(url="https://billing.stripe.com/test_fake_portal_session")


class FakeStripeClient:
    """Mirrors real usage via `client.v1.checkout.sessions`/`client.v1
    .subscriptions`/`client.v1.billing_portal.sessions` — the SDK's newer
    `.v1` namespace, not the deprecated top-level shortcuts
    (`client.checkout`/`client.subscriptions`) this module used until a
    live DeprecationWarning surfaced during S9-03's real checkout test.
    """

    def __init__(self):
        self.created_checkout_params: list[dict] = []
        self.created_portal_params: list[dict] = []
        self.subscription_objects: dict[str, _FakeStripeObject] = {}
        self.v1 = SimpleNamespace(
            checkout=SimpleNamespace(sessions=_FakeCheckoutSessionsAPI(self)),
            subscriptions=_FakeSubscriptionsAPI(self),
            billing_portal=SimpleNamespace(sessions=_FakePortalSessionsAPI(self)),
        )

    def add_subscription(self, subscription_id: str, **fields) -> None:
        """Registers a fake Subscription object `client.subscriptions.retrieve`
        returns for `subscription_id` — used to control what
        `_handle_checkout_completed` sees without a real Stripe API call.
        """
        self.subscription_objects[subscription_id] = _FakeStripeObject(id=subscription_id, **fields)


@pytest.fixture
def fake_stripe_client(monkeypatch) -> FakeStripeClient:
    fake = FakeStripeClient()
    monkeypatch.setattr("app.routers.billing.get_stripe_client", lambda: fake)
    return fake
