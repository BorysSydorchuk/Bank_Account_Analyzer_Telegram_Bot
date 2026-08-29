import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useBillingStatus, useCreateCheckoutSession, useCreatePortalSession } from "@/hooks/useBilling"
import { ApiError } from "@/lib/api"

// S9-05: three distinct states, never a fourth "Upgrade" button that leads
// nowhere — the ticket's own explicit instruction. Paid always gets
// "Manage subscription" regardless of the kill switch (a real paying
// customer must always reach their own real Stripe subscription); free
// only gets "Upgrade" when billing is actually on, otherwise an honest
// note that billing isn't active yet.
export function BillingSection() {
  const { data, isPending } = useBillingStatus()
  const checkoutMutation = useCreateCheckoutSession()
  const portalMutation = useCreatePortalSession()

  const checkoutError = checkoutMutation.isError
    ? checkoutMutation.error instanceof ApiError
      ? checkoutMutation.error.message
      : "Couldn't start checkout. Try again."
    : null
  const portalError = portalMutation.isError
    ? portalMutation.error instanceof ApiError
      ? portalMutation.error.message
      : "Couldn't open the billing portal. Try again."
    : null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold text-text-primary">Billing</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {isPending && <p className="text-sm text-text-secondary">Loading…</p>}

        {data && (
          <>
            <p className="text-sm text-text-secondary">
              Current plan:{" "}
              <span className="font-medium text-text-primary">
                {data.tier === "paid" ? "Mymble Pro" : "Free"}
              </span>
              {data.tier === "paid" && data.status && data.status !== "active" && (
                <span className="ml-1 text-warning">({data.status})</span>
              )}
            </p>

            {data.tier === "paid" ? (
              <>
                <Button
                  size="sm"
                  className="w-fit"
                  onClick={() => portalMutation.mutate()}
                  disabled={portalMutation.isPending}
                >
                  {portalMutation.isPending ? <Loader2 className="size-3.5 animate-spin" /> : "Manage subscription"}
                </Button>
                <p className="text-xs text-text-secondary">
                  Opens Stripe's secure billing portal to update payment details or cancel.
                </p>
              </>
            ) : data.billing_enabled ? (
              <>
                <Button
                  size="sm"
                  className="w-fit"
                  onClick={() => checkoutMutation.mutate()}
                  disabled={checkoutMutation.isPending}
                >
                  {checkoutMutation.isPending ? <Loader2 className="size-3.5 animate-spin" /> : "Upgrade to Mymble Pro"}
                </Button>
                <p className="text-xs text-text-secondary">
                  Higher daily limits on chat, categorization, and insights.
                </p>
              </>
            ) : (
              <p className="text-xs text-text-secondary">
                Billing isn't active yet during the beta — everyone is on the free plan for now.
              </p>
            )}

            {checkoutError && <p className="text-xs text-danger">{checkoutError}</p>}
            {portalError && <p className="text-xs text-danger">{portalError}</p>}
          </>
        )}
      </CardContent>
    </Card>
  )
}
