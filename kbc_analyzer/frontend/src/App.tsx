import { Monitor } from "lucide-react"
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom"

import { Sidebar } from "@/components/layout/Sidebar"
import { ChatPage } from "@/pages/ChatPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { LoginPage } from "@/pages/LoginPage"
import { RegisterPage } from "@/pages/RegisterPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { TransactionsPage } from "@/pages/TransactionsPage"

// The sidebar/mobile-fallback shell every route except /login uses. A
// layout route (rendered via <Outlet/>) rather than repeating this shell
// per page — /login can't use it at all, since it's the one route
// reachable before a session exists (S6-05 adds the actual
// redirect-to-login guard around this shell; it just needs to exist
// separately from /login first).
function AppShell() {
  return (
    <>
      {/* Sprint 1 targets 1024px+ only; below that, a plain message rather
          than a half-broken layout. Tailwind's `lg` breakpoint is 1024px,
          so it lines up exactly with the ticket's minimum width. */}
      <div className="hidden h-screen bg-background font-sans lg:flex">
        <Sidebar />
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
