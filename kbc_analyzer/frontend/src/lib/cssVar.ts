// Resolves a CSS custom property to its actual computed color so it can be
// handed to Recharts' SVG fill/stroke props, which (unlike a plain DOM
// element's style) can't reliably resolve var() themselves. index.css stays
// the one place the hex values are written.
export function resolveCssVar(name: string): string {
  if (typeof window === "undefined") return "#94a3b8"
  const match = /var\((--[\w-]+)\)/.exec(name)
  if (!match) return name
  const value = getComputedStyle(document.documentElement).getPropertyValue(match[1]).trim()
  return value || "#94a3b8"
}
