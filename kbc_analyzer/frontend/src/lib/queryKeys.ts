// Shared between the sync flow (which writes the cache) and every chart
// component (which only ever reads it) — both must use this, not their own
// ad-hoc key, or they'd end up looking at two different cache entries.
export const statisticsKey = (dateFrom: string, dateTo: string) =>
  ["statistics", dateFrom, dateTo] as const
