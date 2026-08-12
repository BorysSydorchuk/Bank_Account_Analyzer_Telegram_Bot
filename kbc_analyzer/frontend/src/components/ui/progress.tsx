import * as React from "react"

import { cn } from "@/lib/utils"
import type { BudgetStatus } from "@/lib/types"

const PROGRESS_FILL_CLASS: Record<BudgetStatus, string> = {
  on_track: "bg-success",
  warning: "bg-warning",
  exceeded: "bg-danger",
}

interface ProgressProps extends React.ComponentProps<"div"> {
  value: number
  status: BudgetStatus
}

function Progress({ value, status, className, ...props }: ProgressProps) {
  const clampedWidth = Math.min(Math.max(value, 0), 100)

  return (
    <div
      data-slot="progress"
      role="progressbar"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}
      {...props}
    >
      <div
        data-slot="progress-fill"
        className={cn("h-full rounded-full transition-[width]", PROGRESS_FILL_CLASS[status])}
        style={{ width: `${clampedWidth}%` }}
      />
    </div>
  )
}

export { Progress }
