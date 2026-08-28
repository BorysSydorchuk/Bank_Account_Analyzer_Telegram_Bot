import { useEffect, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { CheckCircle2, OctagonAlert } from "lucide-react"

import { ApiError, verifyEmail } from "@/lib/api"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

type VerifyStatus = "pending" | "success" | "error"

// S7-09. A layout route outside AppShell, like /login and /register —
// reachable whether or not the visitor currently has a session (the link
// is clicked from an email, possibly on a different device than the one
// they're logged in on, or not logged in at all).
//
// Plain useState/useEffect, not useMutation (found during S8-07's
// onboarding walkthrough): a real, one-time verification link reliably
// hung forever on "Verifying…" in a real browser — the backend actually
// completed the request (confirmed via direct DB query, email_verified
// flipped true) and a raw fetch() or api.ts's verifyEmail() call to the
// same endpoint resolved in milliseconds, but wrapping that same call in
// useMutation().mutate() never settled: no onSuccess, no onError, ever.
// This is a fire-exactly-once side effect on mount with no retry/cache
// need, so useMutation's caching/retry machinery isn't buying anything
// here — direct async state avoids whatever that interaction was.
export function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token")
  // A ref, not useState — found by testing this exact page locally: a
  // state-based guard let the request fire twice (React 18 dev-mode
  // double-effect), and since a verify token is single-use, the second
  // call always 400s even though the first one already succeeded —
  // showing an "invalid or expired" error for a verification that
  // actually worked. A ref is mutated synchronously, immediately, with
  // no re-render/state-update round trip for a second effect run to
  // race against.
  const attemptedRef = useRef(false)

  const [status, setStatus] = useState<VerifyStatus>("pending")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    if (token && !attemptedRef.current) {
      attemptedRef.current = true
      verifyEmail(token)
        .then(() => setStatus("success"))
        .catch((error: unknown) => {
          setErrorMessage(error instanceof ApiError ? error.message : "Something went wrong. Please try again.")
          setStatus("error")
        })
    }
  }, [token])

  return (
    <div className="flex h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center gap-1 text-center">
          <span className="text-lg font-semibold text-primary">Mymble</span>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4 text-center">
          {!token && (
            <>
              <OctagonAlert className="size-8 text-destructive" />
              <p className="text-sm text-foreground">This verification link is missing its token.</p>
            </>
          )}
          {token && status === "pending" && <p className="text-sm text-muted-foreground">Verifying your email…</p>}
          {token && status === "success" && (
            <>
              <CheckCircle2 className="size-8 text-success" />
              <p className="text-sm text-foreground">Your email is verified.</p>
            </>
          )}
          {token && status === "error" && (
            <>
              <OctagonAlert className="size-8 text-destructive" />
              <p className="text-sm text-foreground">{errorMessage}</p>
            </>
          )}
          <Link to="/login" className="text-sm text-primary underline-offset-2 hover:underline">
            Back to sign in
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}
