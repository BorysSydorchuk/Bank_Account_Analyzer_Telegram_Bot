Status: in-progress

================================================================
TICKET S9-03 — Stripe Checkout & Webhook Handling
================================================================

WHAT TO BUILD:
- A real Stripe Checkout flow: user clicks "Upgrade," lands on
  Stripe's real hosted checkout, completes a real test-mode
  payment, gets redirected back
- Webhook endpoint handling the real events that matter:
  checkout completed, subscription updated, subscription
  canceled, payment failed — update S9-02's schema accordingly
- Webhook signature verification (Stripe's standard mechanism)
  — this endpoint is public by necessity, verify Stripe is
  really who's calling it. This is the single most important
  thing in this ticket to get right — a spoofable webhook
  means anyone can grant themselves a free paid subscription
- All of this works correctly regardless of the kill switch —
  the plumbing should be real and correct even while
  enforcement stays off

ACCEPTANCE CRITERIA:
- Real test-mode checkout completes end-to-end
- Webhook correctly updates subscription status for at least:
  successful subscribe, cancellation, failed payment
- Signature verification confirmed rejecting an unsigned/fake
  webhook call — real adversarial test, not just code review
- Real evidence throughout, same standard as every
  credential/payment-adjacent ticket this project has had
- Any deferred/non-blocking finding gets its own standalone
  ledger entry in the same commit, per S9-02's now-working
  pattern

WHEN DONE:
- Real checkout completion evidence
- Real webhook handling evidence for each event type
- Signature verification rejection test — show the actual
  rejected request, not a description
- Do not start S9-04 until confirmed
