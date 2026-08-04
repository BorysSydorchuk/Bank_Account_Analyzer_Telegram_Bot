const currencyFormatter = new Intl.NumberFormat("de-BE", {
  style: "currency",
  currency: "EUR",
})

const currencyFormatterCompact = new Intl.NumberFormat("de-BE", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
})

export function formatAmount(value: number | undefined) {
  return currencyFormatter.format(value ?? 0)
}

// No-decimal variant for axis ticks, where cent-level precision is noise.
export function formatAmountCompact(value: number | undefined) {
  return currencyFormatterCompact.format(value ?? 0)
}