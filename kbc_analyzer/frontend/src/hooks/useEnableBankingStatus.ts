import { useQuery } from "@tanstack/react-query"

import { getEnableBankingStatus } from "@/lib/api"
import type { EnableBankingStatusResponse } from "@/lib/types"

// Unlike useStatistics, this one fetches on its own — there's no sync mutation
// that owns this data. Only ever mounted once (in App.tsx), so there's no risk
// of the duplicate-fetch problem enabled:false exists to avoid elsewhere.
//
// S8-01: data is now an array, one EnableBankingStatus entry per bank Mymble
// supports (see app/institutions.py) — a user can have zero, one, or two
// connections live at once, so a single overall status stopped being
// meaningful once ING joined KBC.
export function useEnableBankingStatus() {
  return useQuery<EnableBankingStatusResponse>({
    queryKey: ["enableBankingStatus"],
    queryFn: getEnableBankingStatus,
    // S7-09: require_verified_email's 403 is never transient — retrying
    // it can't change the outcome, only the user verifying their email
    // can. Without this, React Query's default retry (3 attempts) plus
    // its network-aware pause/resume behavior can end up cycling
    // indefinitely in some environments before ever settling into an
    // error state, leaving isError permanently false and this query
    // stuck reporting isPending — found while testing this exact 403
    // case, not a hypothetical.
    retry: false,
  })
}
