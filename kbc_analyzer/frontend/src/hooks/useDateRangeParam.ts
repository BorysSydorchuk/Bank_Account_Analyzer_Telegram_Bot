import { useCallback, useState } from "react"

export interface RawDateRangeParam {
  dateFrom: string | null
  dateTo: string | null
}

function readFromUrl(): RawDateRangeParam {
  const params = new URLSearchParams(window.location.search)
  return { dateFrom: params.get("date_from"), dateTo: params.get("date_to") }
}

// Reads/writes date_from & date_to as URL query params without pulling in a
// router — this app has exactly one page, so a full router would be dead
// weight. Uses replaceState (not pushState) so picking dates doesn't spam
// the browser's back button with every intermediate selection.
export function useDateRangeParam() {
  const [range, setRangeState] = useState<RawDateRangeParam>(readFromUrl)

  const setRange = useCallback((dateFrom: string, dateTo: string) => {
    const params = new URLSearchParams(window.location.search)
    params.set("date_from", dateFrom)
    params.set("date_to", dateTo)
    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`)
    setRangeState({ dateFrom, dateTo })
  }, [])

  return { dateFrom: range.dateFrom, dateTo: range.dateTo, setRange }
}
