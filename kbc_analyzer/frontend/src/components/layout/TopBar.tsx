import { SyncControls } from "@/components/dashboard/SyncControls"
import type { useDashboard } from "@/hooks/useDashboard"

interface TopBarProps {
  dashboard: ReturnType<typeof useDashboard>
}

export function TopBar({ dashboard }: TopBarProps) {
  return (
    <header className="flex items-center justify-between border-b border-border bg-card px-6 py-4">
      <h1 className="text-xl font-semibold text-text-primary">Dashboard</h1>
      <SyncControls {...dashboard} />
    </header>
  )
}
