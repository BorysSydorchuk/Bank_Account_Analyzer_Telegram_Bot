interface CategoryPillProps {
  category: string | null
  color: string | undefined
}

// color is a real hex value from the categories table (S3-01) — the exact
// same source the donut chart reads, so a category's pill here always
// matches its slice color there.
export function CategoryPill({ category, color }: CategoryPillProps) {
  if (!category) {
    return <span className="text-xs text-text-secondary">—</span>
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
    </span>
  )
}
