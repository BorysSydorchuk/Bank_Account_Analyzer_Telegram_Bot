import { useEffect, useRef } from "react"
import { useMutation } from "@tanstack/react-query"
import { Link, useSearchParams } from "react-router-dom"
import { CheckCircle2, OctagonAlert } from "lucide-react"

import { ApiError, verifyEmail } from "@/lib/api"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

// S7-09. A layout route outside AppShell, like /login and /register —
// reachable whether or not the visitor currently has a session (the link
// is clicked from an email, possibly on a different device than the one
// they're logged in on, or not logged in at all).
export function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token")
  // A ref, not useState — found by testing this exact page locally: a
  // state-based guard let the mutation fire twice (React 18 dev-mode
  // double-effect), and since a verify token is single-use, the second
  // call always 400s even though the first one already succeeded —
  // showing an "invalid or expired" error for a verification that
  // actually worked. A ref is mutated synchronously, immediately, with
  // no re-render/state-update round trip for a second effect run to
  // race against.
  const attemptedRef = useRef(false)

  const verifyMutation = useMutation({
    mutationFn: () => verifyEmail(token ?? ""),
  })

  useEffect(() => {
    if (token && !attemptedRef.current) {
      attemptedRef.current = true
      verifyMutation.mutate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const errorMessage =
    verifyMutation.isError && verifyMutation.error instanceof ApiError
      ? verifyMutation.error.message
      : verifyMutation.isError
        ? "Something went wrong. Please try again."
        : null

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
          {token && verifyMutation.isPending && <p className="text-sm text-muted-foreground">Verifying your email…</p>}
          {token && verifyMutation.isSuccess && (
            <>
              <CheckCircle2 className="size-8 text-success" />
              <p className="text-sm text-foreground">Your email is verified.</p>
            </>
          )}
          {token && verifyMutation.isError && (
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
