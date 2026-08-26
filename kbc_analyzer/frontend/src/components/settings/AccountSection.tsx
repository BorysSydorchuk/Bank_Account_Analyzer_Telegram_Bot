import { useSearchParams } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useCurrentUser } from "@/hooks/useCurrentUser"

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

// S6-07 finding 1: the only place a password account can attach a Google
// identity is this explicit, authenticated action — never as a side
// effect of a Google sign-in attempt (see routers/user_auth.py's
// google_callback). A plain <a>, not a fetch, for the same reason
// LoginPage's Google button is — a real top-level navigation through
// Google's consent screen, which a CORS-bound fetch can't follow.
const CONNECT_GOOGLE_URL = `${API_URL}/api/auth/google/link`

export function AccountSection() {
  const { data: user } = useCurrentUser()
  const [searchParams] = useSearchParams()
  const linked = searchParams.get("linked") === "google"
  const linkFailed = searchParams.get("error") === "google_link_failed"

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold text-text-primary">Account</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {user && <p className="text-sm text-text-secondary">Signed in as {user.email}</p>}
        {user && !user.email_verified && (
          // S7-09: the only visible cue an unverified account has —
          // there's no resend-link button (out of this ticket's scope,
          // flagged in docs/verification_debt.md), so this just states
          // what's true rather than offering an action that doesn't exist.
          <p className="text-xs text-warning">Email not verified — check your inbox for the verification link.</p>
        )}
        {linked && <p className="text-xs text-success">Google account connected.</p>}
        {linkFailed && (
          <p className="text-xs text-danger">
            Couldn't connect that Google account — it may already be linked elsewhere.
          </p>
        )}
        <Button asChild size="sm" variant="outline" className="w-fit">
          <a href={CONNECT_GOOGLE_URL}>Connect Google account</a>
        </Button>
      </CardContent>
    </Card>
  )
}
