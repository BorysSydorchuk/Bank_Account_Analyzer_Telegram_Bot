import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Link } from "react-router-dom"

import { requestPasswordReset } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

const INPUT_CLASSES =
  "h-9 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

// S7-09, replacing S6-04's "not available yet" placeholder note.
export function ForgotPasswordPage() {
  const [email, setEmail] = useState("")

  const requestMutation = useMutation({
    mutationFn: () => requestPasswordReset(email),
  })

  return (
    <div className="flex h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center gap-1 text-center">
          <span className="text-lg font-semibold text-primary">Mymble</span>
          <p className="text-sm text-muted-foreground">Reset your password.</p>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {requestMutation.isSuccess ? (
            // Deliberately the same message regardless of whether the email
            // actually had an account — the backend's own response never
            // reveals that, so neither should this page (routers/user_auth.py's
            // request_password_reset).
            <p className="text-sm text-foreground">
              If an account exists for that email, we've sent a password reset link.
            </p>
          ) : (
            <form
              className="flex flex-col gap-3"
              onSubmit={(e) => {
                e.preventDefault()
                requestMutation.mutate()
              }}
            >
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-foreground" htmlFor="forgot-password-email">
                  Email
                </label>
                <input
                  id="forgot-password-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={INPUT_CLASSES}
                />
              </div>
              <Button type="submit" size="lg" className="h-10 w-full" disabled={requestMutation.isPending}>
                {requestMutation.isPending ? "Sending…" : "Send reset link"}
              </Button>
            </form>
          )}

          <p className="text-center text-sm text-muted-foreground">
            <Link to="/login" className="text-primary underline-offset-2 hover:underline">
              Back to sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
