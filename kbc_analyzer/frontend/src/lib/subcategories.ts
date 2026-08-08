// Mirrors backend/app/agents/categorization.py's SUBCATEGORIES_OF_* constants.
// Kept in sync by hand, same as this file's other backend-mirrored types —
// only these two categories carry a fixed subcategory list.
export const SUBCATEGORIES_BY_CATEGORY: Record<string, string[]> = {
  Other: ["Entertainment", "Health", "Shopping", "Utilities & Bills", "Rest", "Subscriptions"],
  Traveling: ["Transport", "Housing", "Food", "Entertainment"],
}
