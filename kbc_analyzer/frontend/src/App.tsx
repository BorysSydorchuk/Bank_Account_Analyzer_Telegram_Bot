import { Monitor } from "lucide-react"
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom"

import { Sidebar } from "@/components/layout/Sidebar"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { ChatPage } from "@/pages/ChatPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage"
import { LoginPage } from "@/pages/LoginPage"
import { RegisterPage } from "@/pages/RegisterPage"
import { ResetPasswordPage } from "@/pages/ResetPasswordPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { TransactionsPage } from "@/pages/TransactionsPage"
import { VerifyEmailPage } from "@/pages/VerifyEmailPage"

// The sidebar/mobile-fallback shell every route except /login and
// /register uses — and, as of S6-05, the actual redirect-to-login guard:
// GET /api/auth/me runs once on mount; any failure (no session, expired
// session — see useCurrentUser's docstring for why every error is
// treated the same) sends the visitor to /login instead of rendering
// whatever page they asked for. A layout route (rendered via <Outlet/>)
// rather than repeating this shell/check per page.
function AppShell() {
  const { data: user, isPending, isError } = useCurrentUser()

  if (isPending) {
    // No spinner/skeleton here on purpose — this resolves in one fast
    // local request (Redis-backed session lookup), and a flash of
    // loading UI before either the app or /login would be more jarring
    // than a blank frame for that long.
    return null
  }

  if (isError) {
    return <Navigate to="/login" replace />
  }

  return (
    <>
      {/* Sprint 1 targets 1024px+ only; below that, a plain message rather
          than a half-broken layout. Tailwind's `lg` breakpoint is 1024px,
          so it lines up exactly with the ticket's minimum width. */}
      <div className="hidden h-screen bg-background font-sans lg:flex">
        <Sidebar user={user} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Outlet />
        </div>
      </div>

      <div className="flex h-screen items-center justify-center bg-background p-6 text-center lg:hidden">
        <div className="flex max-w-sm flex-col items-center gap-3 rounded-xl border border-border bg-card p-8 shadow-sm">
          <Monitor className="size-8 text-primary" />
          <span className="text-lg font-semibold text-primary">KBC Analyzer</span>
          <p className="text-sm text-text-secondary">KBC Analyzer is best viewed on a larger screen.</p>
        </div>
      </div>
    </>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
