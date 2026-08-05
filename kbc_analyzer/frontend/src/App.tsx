import { BrowserRouter, Route, Routes } from "react-router-dom"

import { Sidebar } from "@/components/layout/Sidebar"
import { DashboardPage } from "@/pages/DashboardPage"
import { SettingsPage } from "@/pages/SettingsPage"

function App() {
  return (
    <BrowserRouter>
      {/* Sprint 1 targets 1024px+ only; below that, a plain message rather
          than a half-broken layout. Tailwind's `lg` breakpoint is 1024px,
          so it lines up exactly with the ticket's minimum width. */}
      <div className="hidden h-screen bg-background font-sans lg:flex">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </div>
      </div>

      <div className="flex h-screen items-center justify-center bg-background p-6 text-center lg:hidden">
        <p className="text-text-secondary">
          This dashboard is best viewed on a desktop screen (1024px or wider).
        </p>
      </div>
    </BrowserRouter>
  )
}

export default App
