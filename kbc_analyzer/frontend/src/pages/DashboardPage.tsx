import { BudgetsWidget } from "@/components/dashboard/BudgetsWidget"
import { CategoryBreakdown } from "@/components/dashboard/CategoryBreakdown"
import { InsightsPanel } from "@/components/dashboard/InsightsPanel"
import { SpendingOverTime } from "@/components/dashboard/SpendingOverTime"
import { SummaryCards } from "@/components/dashboard/SummaryCards"
import { SessionBanner } from "@/components/layout/SessionBanner"
import { TopBar } from "@/components/layout/TopBar"
import { useDashboard } from "@/hooks/useDashboard"

export function DashboardPage() {
  const dashboard = useDashboard()

  return (
    <>
      <TopBar dashboard={dashboard} />
      <SessionBanner />
      <main className="flex-1 overflow-y-auto bg-background p-6">
        <SummaryCards
          dateFrom={dashboard.dateFrom}
          dateTo={dashboard.dateTo}
          isSyncing={dashboard.isSyncing}
        />
        <BudgetsWidget />
        <CategoryBreakdown
          dateFrom={dashboard.dateFrom}
          dateTo={dashboard.dateTo}
          isSyncing={dashboard.isSyncing}
        />
        <SpendingOverTime
          dateFrom={dashboard.dateFrom}
          dateTo={dashboard.dateTo}
          isSyncing={dashboard.isSyncing}
        />
        <InsightsPanel
          dateFrom={dashboard.dateFrom}
          dateTo={dashboard.dateTo}
          isSyncing={dashboard.isSyncing}
        />
      </main>
    </>
  )
}
