import { CategoryBreakdown } from "@/components/dashboard/CategoryBreakdown"
import { SummaryCards } from "@/components/dashboard/SummaryCards"
import { Sidebar } from "@/components/layout/Sidebar"
import { TopBar } from "@/components/layout/TopBar"
import { useDashboard } from "@/hooks/useDashboard"

function App() {
  // Called once, here — TopBar/SyncControls and SummaryCards both receive
  // this same instance as props so they read one shared date range and
  // sync state instead of each running their own auto-sync effect.
  const dashboard = useDashboard()

  return (
    <>
      {/* Sprint 1 targets 1024px+ only; below that, a plain message rather
          than a half-broken layout. Tailwind's `lg` breakpoint is 1024px,
          so it lines up exactly with the ticket's minimum width. */}
      <div className="hidden h-screen bg-background font-sans lg:flex">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar dashboard={dashboard} />
          <main className="flex-1 overflow-y-auto bg-background p-6">
            <SummaryCards
              dateFrom={dashboard.dateFrom}
              dateTo={dashboard.dateTo}
              isSyncing={dashboard.isSyncing}
            />
            <CategoryBreakdown
              dateFrom={dashboard.dateFrom}
              dateTo={dashboard.dateTo}
              isSyncing={dashboard.isSyncing}
            />
            {/* S1-08 mounts below this */}
          </main>
        </div>
      </div>

      <div className="flex h-screen items-center justify-center bg-background p-6 text-center lg:hidden">
        <p className="text-text-secondary">
          This dashboard is best viewed on a desktop screen (1024px or wider).
        </p>
      </div>
    </>
  )
}

export default App
