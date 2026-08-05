import { NavLink } from "react-router-dom"

import { cn } from "@/lib/utils"

// Transactions gets its real page in S2-07 — until then it's a styled
// placeholder (no `to`), same look as before wiring in routes.
const NAV_ITEMS: { label: string; to: string | null }[] = [
  { label: "Dashboard", to: "/" },
  { label: "Transactions", to: null },
  { label: "Settings", to: "/settings" },
]

export function Sidebar() {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-card">
      <div className="px-6 py-5">
        <span className="text-lg font-semibold text-primary">KBC Analyzer</span>
      </div>
      <nav className="flex flex-col gap-1 px-3">
        {NAV_ITEMS.map((item) =>
          item.to ? (
            <NavLink
              key={item.label}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-text-secondary hover:bg-muted hover:text-text-primary"
                )
              }
            >
              {item.label}
            </NavLink>
          ) : (
            <span
              key={item.label}
              className="rounded-lg px-3 py-2 text-sm font-medium text-text-secondary"
            >
              {item.label}
            </span>
          )
        )}
      </nav>
    </aside>
  )
}
