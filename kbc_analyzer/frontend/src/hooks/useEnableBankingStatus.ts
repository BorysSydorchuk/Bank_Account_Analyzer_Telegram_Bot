import { useQuery } from "@tanstack/react-query"

import { getEnableBankingStatus } from "@/lib/api"
import type { EnableBankingStatusResponse } from "@/lib/types"

// Unlike useStatistics, this one fetches on its own — there's no sync mutation
// that owns this data. Only ever mounted once (in App.tsx), so there's no risk
// of the duplicate-fetch problem enabled:false exists to avoid elsewhere.
export function useEnableBankingStatus() {
  return useQuery<EnableBankingStatusResponse>({
    queryKey: ["enableBankingStatus"],
    queryFn: getEnableBankingStatus,
  })
}
