import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Link, useSearchParams } from "react-router-dom"

import { ApiError, login } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

// A plain <a>, not a fetch/onClick handler — signing in with Google is a
// real top-level browser navigation to the backend's redirect endpoint
// (routers/user_auth.py's GET /api/auth/google/login), which itself
// redirects on to Google. Driving this through fetch() would just be a
// CORS request that can't follow a cross-origin redirect chain the way a
// real navigation does.
const GOOGLE_LOGIN_URL = `${API_URL}/api/auth/google/login`

// routers/user_auth.py's google_callback redirects here with this exact
// query string on any failure (denied consent, expired/reused code,
// state mismatch) — one generic message rather than echoing Google's own
// error detail, which could otherwise leak implementation detail to
// whoever's looking at the URL bar.
const ERROR_MESSAGES: Record<string, string> = {
  google_sign_in_failed: "Google sign-in didn't go through. Please try again.",
}

const INPUT_CLASSES =
  "h-9 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

export function LoginPage() {
  const [searchParams] = useSearchParams()
  const googleErrorCode = searchParams.get("error")
  const googleErrorMessage = googleErrorCode
    ? (ERROR_MESSAGES[googleErrorCode] ?? "Sign-in failed. Please try again.")
    : null

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  // Not a route — S6-04 explicitly has no email infrastructure to send a
  // reset link through yet. A dead/broken link would be worse than
  // admitting the feature isn't there; this just says so, inline.
  const [showForgotPasswordNote, setShowForgotPasswordNote] = useState(false)

  const loginMutation = useMutation({
    mutationFn: () => login(email, password),
    // A full reload, not client-side navigation — the app has no notion
    // of "the current user" in memory yet (that's S6-05/S6-06), so the
    // simplest correct thing after establishing a session is to just
    // reload into the app fresh.
    onSuccess: () => {
      window.location.href = "/"
    },
  })

  const loginErrorMessage =
    loginMutation.isError && loginMutation.error instanceof ApiError
      ? loginMutation.error.message
      : loginMutation.isError
        ? "Something went wrong. Please try again."
        : null

  return (
    <div className="flex h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center gap-1 text-center">
          <span className="text-lg font-semibold text-primary">KBC Analyzer</span>
          <p className="text-sm text-muted-foreground">Sign in to see your dashboard.</p>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {googleErrorMessage && (
            <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {googleErrorMessage}
            </p>
          )}

          <Button asChild size="lg" className="h-10 w-full">
            <a href={GOOGLE_LOGIN_URL}>
              <GoogleIcon />
              Sign in with Google
            </a>
          </Button>

          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <div className="h-px flex-1 bg-border" />
            or
            <div className="h-px flex-1 bg-border" />
          </div>

          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault()
              loginMutation.mutate()
            }}
          >
            {loginErrorMessage && (
              <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {loginErrorMessage}
              </p>
            )}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-foreground" htmlFor="login-email">
                Email
              </label>
              <input
                id="login-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={INPUT_CLASSES}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between">
                <label className="text-sm font-medium text-foreground" htmlFor="login-password">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setShowForgotPasswordNote((shown) => !shown)}
                  className="text-xs text-muted-foreground underline-offset-2 hover:underline"
                >
                  Forgot password?
                </button>
              </div>
              <input
                id="login-password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={INPUT_CLASSES}
              />
              {showForgotPasswordNote && (
                <p className="text-xs text-muted-foreground">
                  Password reset isn't available yet — contact support for help getting back in.
                </p>
              )}
            </div>
            <Button type="submit" size="lg" className="h-10 w-full" disabled={loginMutation.isPending}>
              {loginMutation.isPending ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground">
            No account yet?{" "}
            <Link to="/register" className="text-primary underline-offset-2 hover:underline">
              Create one
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

// Google's own multi-color "G" mark — brand-specific, not a design-token
// color, so it's the one deliberate exception to this app's "no hardcoded
// hex values" rule (CLAUDE.md): a single-color rendering of Google's logo
// isn't Google's logo.
function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.47c-.28 1.5-1.13 2.77-2.4 3.62v3h3.88c2.27-2.09 3.57-5.17 3.57-8.81Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.96-1.07 7.95-2.92l-3.88-3c-1.08.72-2.45 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.96H1.27v3.1C3.25 21.3 7.31 24 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.27a7.2 7.2 0 0 1 0-4.54v-3.1H1.27a12 12 0 0 0 0 10.74l4-3.1Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.76 0 3.34.6 4.58 1.79l3.44-3.44C17.95 1.19 15.24 0 12 0 7.31 0 3.25 2.7 1.27 6.63l4 3.1C6.22 6.87 8.87 4.75 12 4.75Z"
      />
    </svg>
  )
}
