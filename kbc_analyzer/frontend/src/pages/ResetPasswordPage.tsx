import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Link, useSearchParams } from "react-router-dom"

import { ApiError, resetPassword } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

const INPUT_CLASSES =
  "h-9 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

// S7-09. Reachable whether or not the visitor has a session — the link
// is clicked from an email, same reasoning as VerifyEmailPage.
export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token")
  const [password, setPassword] = useState("")

  const resetMutation = useMutation({
    mutationFn: () => resetPassword(token ?? "", password),
    onSuccess: () => {
      window.location.href = "/login"
    },
  })

  const errorMessage =
    resetMutation.isError && resetMutation.error instanceof ApiError
      ? resetMutation.error.message
      : resetMutation.isError
        ? "Something went wrong. Please try again."
        : null

  return (
    <div className="flex h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center gap-1 text-center">
          <span className="text-lg font-semibold text-primary">Mymble</span>
          <p className="text-sm text-muted-foreground">Set a new password.</p>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {!token ? (
            <p className="text-sm text-destructive">This reset link is missing its token.</p>
          ) : (
            <form
              className="flex flex-col gap-3"
              onSubmit={(e) => {
                e.preventDefault()
                resetMutation.mutate()
              }}
            >
              {errorMessage && (
                <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {errorMessage}
                </p>
              )}
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-foreground" htmlFor="reset-password-new">
                  New password
                </label>
                <input
                  id="reset-password-new"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={INPUT_CLASSES}
                />
                <p className="text-xs text-muted-foreground">At least 8 characters.</p>
              </div>
              <Button type="submit" size="lg" className="h-10 w-full" disabled={resetMutation.isPending}>
                {resetMutation.isPending ? "Resetting…" : "Reset password"}
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
