import { useMutation, useQuery } from "@tanstack/react-query"

import { createCheckoutSession, createPortalSession, getBillingStatus } from "@/lib/api"
import type { BillingStatus } from "@/lib/types"

export const billingStatusKey = ["billing", "status"] as const

export function useBillingStatus() {
  return useQuery<BillingStatus>({
    queryKey: billingStatusKey,
    queryFn: getBillingStatus,
  })
}

// Both mutations redirect the whole browser to a real Stripe-hosted page
// on success — there's nothing to invalidate/render locally afterward,
// the user is leaving this app for the duration of checkout/portal.
export function useCreateCheckoutSession() {
  return useMutation({
    mutationFn: createCheckoutSession,
    onSuccess: (data) => {
      window.location.href = data.checkout_url
    },
  })
}

export function useCreatePortalSession() {
  return useMutation({
    mutationFn: createPortalSession,
    onSuccess: (data) => {
      window.location.href = data.portal_url
    },
  })
}
