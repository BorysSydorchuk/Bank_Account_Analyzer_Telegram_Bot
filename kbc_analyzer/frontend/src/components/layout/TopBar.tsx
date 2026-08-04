import { SyncControls } from "@/components/dashboard/SyncControls"

export function TopBar() {
  return (
    <header className="flex items-center justify-between border-b border-border bg-card px-6 py-4">
      <h1 className="text-xl font-semibold text-text-primary">Dashboard</h1>
      <SyncControls />
    </header>
  )
}
