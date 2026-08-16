import { NavLink } from "react-router-dom"

import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { label: "Dashboard", to: "/" },
  { label: "Chat", to: "/chat" },
  { label: "Transactions", to: "/transactions" },
  { label: "Settings", to: "/settings" },
]

export function Sidebar() {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-card">
      <div className="px-6 py-5">
        <span className="text-lg font-semibold text-primary">KBC Analyzer</span>
      </div>
      <nav className="flex flex-col gap-1 px-3">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.label}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "cursor-pointer rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  // bg-primary/10 (a tint of the existing --primary token,
                  // not a new hardcoded hex) lands within a couple RGB
                  // points of the ticket's literal #EFF6FF.
                  : "text-text-secondary hover:bg-primary/10 hover:text-primary"
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
