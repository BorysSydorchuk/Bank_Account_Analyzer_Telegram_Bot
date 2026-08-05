import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { getSettings, patchSettings } from "@/lib/api"
import type { SettingsResponse } from "@/lib/types"

export const settingsKey = ["settings"] as const

export function useSettings() {
  return useQuery<SettingsResponse>({
    queryKey: settingsKey,
    queryFn: getSettings,
  })
}

export function usePatchSetting() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) => patchSettings(key, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKey })
    },
  })
}
