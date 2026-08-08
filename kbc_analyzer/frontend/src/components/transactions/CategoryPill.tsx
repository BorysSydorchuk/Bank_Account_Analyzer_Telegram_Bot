import { Pencil } from "lucide-react"

interface CategoryPillProps {
  category: string | null
  color: string | undefined
  // True once a human has corrected this row (S3-05) — shown as a small
  // badge so the pill itself explains why the AI won't touch it again.
  manuallyEdited?: boolean
}

const EDITED_TOOLTIP = "Manually edited — won't be overwritten by AI"

function EditedBadge() {
  return (
    <span title={EDITED_TOOLTIP} className="inline-flex shrink-0">
      <Pencil className="size-2.5 opacity-70" aria-label={EDITED_TOOLTIP} />
    </span>
  )
}

// color is a real hex value from the categories table (S3-01) — the exact
// same source the donut chart reads, so a category's pill here always
// matches its slice color there.
export function CategoryPill({ category, color, manuallyEdited }: CategoryPillProps) {
  if (!category) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-text-secondary">
        —{manuallyEdited && <EditedBadge />}
      </span>
    )
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
      style={{
        backgroundColor: color ? `color-mix(in srgb, ${color} 16%, white)` : undefined,
        color: color,
      }}
    >
      <span className="size-1.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      {category}
      {manuallyEdited && <EditedBadge />}
    </span>
  )
}
