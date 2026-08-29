import { Link } from "react-router-dom"
import { OctagonAlert } from "lucide-react"

import { Card, CardContent, CardHeader } from "@/components/ui/card"

// S9-05 — Stripe's real cancel_url. Nothing changed server-side (no
// subscriptions row was ever written for an abandoned checkout — see
// app/routers/billing.py's module docstring), so this page is purely
// informational.
export function BillingCancelPage() {
  return (
    <div className="flex h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center gap-1 text-center">
          <span className="text-lg font-semibold text-primary">Mymble</span>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4 text-center">
          <OctagonAlert className="size-8 text-muted-foreground" />
          <p className="text-sm text-foreground">Checkout was canceled — you're still on the free plan.</p>
          <Link to="/settings" className="text-sm text-primary underline-offset-2 hover:underline">
            Back to Settings
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}
