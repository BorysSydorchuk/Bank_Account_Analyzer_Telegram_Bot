import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Link } from "react-router-dom"

import { ApiError, register } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

const INPUT_CLASSES =
  "h-9 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

export function RegisterPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  const registerMutation = useMutation({
    mutationFn: () => register(email, password),
    // Same reasoning as LoginPage's onSuccess — no in-memory "current
    // user" concept exists yet, so a full reload into the app is the
    // simplest correct thing once registration also creates a session.
    onSuccess: () => {
      window.location.href = "/"
    },
  })

  const errorMessage =
    registerMutation.isError && registerMutation.error instanceof ApiError
      ? registerMutation.error.message
      : registerMutation.isError
        ? "Something went wrong. Please try again."
        : null

  return (
    <div className="flex h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center gap-1 text-center">
          <span className="text-lg font-semibold text-primary">Mymble</span>
          <p className="text-sm text-muted-foreground">Create an account to get started.</p>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault()
              registerMutation.mutate()
            }}
          >
            {errorMessage && (
              <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {errorMessage}
              </p>
            )}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-foreground" htmlFor="register-email">
                Email
              </label>
              <input
                id="register-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={INPUT_CLASSES}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-foreground" htmlFor="register-password">
                Password
              </label>
              <input
                id="register-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={INPUT_CLASSES}
              />
              {/* Matches app/auth/password.py's MIN_PASSWORD_LENGTH exactly
                  — the backend is still the real enforcement point (this
                  is just so a user finds out at 7 characters, not after
                  submitting). */}
              <p className="text-xs text-muted-foreground">At least 8 characters.</p>
            </div>
            <Button type="submit" size="lg" className="h-10 w-full" disabled={registerMutation.isPending}>
              {registerMutation.isPending ? "Creating account…" : "Create account"}
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link to="/login" className="text-primary underline-offset-2 hover:underline">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
