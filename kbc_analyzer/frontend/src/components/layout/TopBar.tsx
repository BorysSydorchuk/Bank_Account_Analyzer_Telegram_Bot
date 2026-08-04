// The grey rectangle stands in for the date-range picker + sync button that
// S1-05 replaces — this ticket only builds the shell they'll mount into.
export function TopBar() {
  return (
    <header className="flex items-center justify-between border-b border-border bg-card px-6 py-4">
      <h1 className="text-xl font-semibold text-text-primary">Dashboard</h1>
      <div className="h-9 w-64 rounded-md bg-muted" aria-hidden="true" />
    </header>
  )
}
