import { useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { CheckCircle2 } from "lucide-react"

import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { billingStatusKey } from "@/hooks/useBilling"

// S9-05 — Stripe's real success_url (app/routers/billing.py's
// create_checkout_session). A layout route outside AppShell, like
// /verify-email — the visitor is landing here straight off Stripe's own
// domain, not navigating from inside the app.
//
// S9-06 finding (Reviewer, S9-05): this page's original comment claimed
// the webhook (S9-03) had "already happened" by the time Stripe redirects
// here — that's not something Stripe guarantees. The redirect and the
// webhook delivery are two independent async outcomes of the same
// checkout completion; the webhook can genuinely still be in flight when
// this page mounts. invalidateQueries below refetches immediately, with
// no retry/poll — a real (rare, self-correcting) race where this page's
// hardcoded "You're on Mymble Pro" can momentarily outrun the actual
// tier flip, and a visitor who clicks straight back to Settings sees
// "Free" until something else (a manual reload, TanStack Query's
// refetch-on-window-focus) triggers another fetch. Logged as its own
// entry in docs/verification_debt.md rather than silently fixed here —
// see that entry for the retry/poll approach that would close it.

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
