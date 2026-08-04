const currencyFormatter = new Intl.NumberFormat("de-BE", {
  style: "currency",
  currency: "EUR",
})

export function formatAmount(value: number | undefined) {
  return currencyFormatter.format(value ?? 0)
}