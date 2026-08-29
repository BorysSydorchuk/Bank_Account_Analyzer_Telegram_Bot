import { useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { CheckCircle2 } from "lucide-react"

import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { billingStatusKey } from "@/hooks/useBilling"

// S9-05 — Stripe's real success_url (app/routers/billing.py's
// create_checkout_session). A layout route outside AppShell, like
// /verify-email — the visitor is landing here straight off Stripe's own
// domain, not navigating from inside the app. The real tier flip already
// happened server-side via the checkout.session.completed webhook (S9-03)
// before Stripe even redirects here, so this page has nothing to poll or
// verify itself — it just invalidates the cached billing status so
// Settings shows the new plan immediately instead of a stale "Free".
export function BillingSuccessPage() {
  const queryClient = useQueryClient()

  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: billingStatusKey })
  }, [queryClient])

  return (
    <div className="flex h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center gap-1 text-center">
          <span className="text-lg font-semibold text-primary">Mymble</span>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4 text-center">
          <CheckCircle2 className="size-8 text-success" />
          <p className="text-sm text-foreground">You're on Mymble Pro. Welcome aboard.</p>
          <Link to="/settings" className="text-sm text-primary underline-offset-2 hover:underline">
            Back to Settings
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}
