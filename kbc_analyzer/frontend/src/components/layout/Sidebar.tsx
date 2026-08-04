import { cn } from "@/lib/utils"

// Real routing arrives with later tickets — for now these are visual
// placeholders, with "Dashboard" shown active since it's the only page.
const NAV_ITEMS = [
  { label: "Dashboard", active: true },
  { label: "Transactions", active: false },
  { label: "Settings", active: false },
]

export function Sidebar() {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-card">
      <div className="px-6 py-5">
        <span className="text-lg font-semibold text-primary">KBC Analyzer</span>
      </div>
      <nav className="flex flex-col gap-1 px-3">
        {NAV_ITEMS.map((item) => (
          <a
            key={item.label}
            href="#"
            aria-current={item.active ? "page" : undefined}
            className={cn(
              "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              item.active
                ? "bg-primary text-primary-foreground"
                : "text-text-secondary hover:bg-muted hover:text-text-primary",
            )}
          >
            {item.label}
          </a>
        ))}
      </nav>
    </aside>
  )
}
