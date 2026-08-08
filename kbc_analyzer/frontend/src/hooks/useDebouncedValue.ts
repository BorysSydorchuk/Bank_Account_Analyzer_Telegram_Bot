import { useEffect, useState } from "react"

// Generic — used by the Transactions page's global search (S3-07 Item 4) to
// avoid firing a request on every keystroke, but not tied to search
// specifically in case something else needs the same debounce later.
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}
