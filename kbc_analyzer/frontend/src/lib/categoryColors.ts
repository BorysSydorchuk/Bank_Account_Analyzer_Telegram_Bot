const PALETTE_SIZE = 8

// A stable starting point per category name, not its position in a sorted/
// filtered list — so a category leans toward the same color across syncs
// even as totals (and therefore sort order) change between date ranges.
function hashCategoryName(name: string): number {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0
  }
  return Math.abs(hash)
}

// Assigns every category in the current set a color slot, resolving hash
// collisions by probing to the next free slot — so up to 8 categories always
// get 8 *distinct* colors (the ticket's "each category gets a distinct
// color" requirement), only falling back to a shared/cycled color past 8.
// Resolution order is alphabetical (not by total) so it doesn't reshuffle
// just because one category overtook another between syncs.
export function assignCategoryColors(categoryNames: string[]): Map<string, string> {
  const ordered = [...new Set(categoryNames)].sort((a, b) => a.localeCompare(b))
  const usedSlots = new Set<number>()
  const slotByCategory = new Map<string, number>()

  for (const name of ordered) {
    let slot = hashCategoryName(name) % PALETTE_SIZE
    if (usedSlots.size < PALETTE_SIZE) {
      let probes = 0
      while (usedSlots.has(slot) && probes < PALETTE_SIZE) {
        slot = (slot + 1) % PALETTE_SIZE
        probes++
      }
    }
    usedSlots.add(slot)
    slotByCategory.set(name, slot)
  }

  const colorByCategory = new Map<string, string>()
  for (const [name, slot] of slotByCategory) {
    // The raw token, not the `--color-category-*` Tailwind-utility alias in
    // index.css's @theme block — @theme inline only emits aliases for utility
    // classes (bg-*, text-*), not as real :root custom properties, so this is
    // the one actually readable via getComputedStyle at runtime.
    colorByCategory.set(name, `var(--category-${slot + 1})`)
  }
  return colorByCategory
}