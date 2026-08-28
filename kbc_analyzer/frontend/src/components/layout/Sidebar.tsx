import { LogOut } from "lucide-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { NavLink } from "react-router-dom"

import { logout } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { UserOut } from "@/lib/types"

const NAV_ITEMS = [
  { label: "Dashboard", to: "/" },
  { label: "Chat", to: "/chat" },
  { label: "Transactions", to: "/transactions" },
  { label: "Feedback", to: "/feedback" },
  { label: "Settings", to: "/settings" },
]

export function Sidebar({ user }: { user: UserOut }) {
  const queryClient = useQueryClient()
  const logoutMutation = useMutation({
    mutationFn: logout,
    // Clears every cached query, not just current-user — the next visitor
    // on this browser (or this same person logging back in as someone
    // else) should never see a stale query still holding the previous
    // session's data. A full reload, not client-side navigation, for the
    // same reason App.tsx's AppShell has no in-memory "current user"
    // beyond this one query.
    onSuccess: () => {
      queryClient.clear()
      window.location.href = "/login"
    },
  })

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-card">
      <div className="px-6 py-5">
        <span className="text-lg font-semibold text-primary">Mymble</span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 px-3">
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
      <div className="flex items-center gap-2 border-t border-border px-4 py-3">
        <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
          {user.email.charAt(0).toUpperCase()}
        </div>
        <span className="min-w-0 flex-1 truncate text-sm text-text-secondary" title={user.email}>
          {user.email}
        </span>
        <button
          type="button"
          onClick={() => logoutMutation.mutate()}
          disabled={logoutMutation.isPending}
          title="Sign out"
          className="flex size-7 shrink-0 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-destructive/10 hover:text-destructive"
        >
          <LogOut className="size-4" />
        </button>
      </div>
    </aside>
  )
}
