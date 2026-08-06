interface CategoryPillProps {
  category: string | null
  colorVar: string | undefined
}

// colorVar is one of index.css's --category-N tokens (see lib/categoryColors.ts)
// — the exact same source S1-07's donut chart reads, so a category's pill here
// always matches its slice color there.
export function CategoryPill({ category, colorVar }: CategoryPillProps) {
  if (!category) {
    return <span className="text-xs text-text-secondary">—</span>
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
      style={{
        backgroundColor: colorVar ? `color-mix(in srgb, ${colorVar} 16%, white)` : undefined,
        color: colorVar,
      }}
    >
      <span className="size-1.5 shrink-0 rounded-full" style={{ backgroundColor: colorVar }} />
      {category}
    </span>
  )
}
