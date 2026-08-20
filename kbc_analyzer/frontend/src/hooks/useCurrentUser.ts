import { useQuery } from "@tanstack/react-query"

import { getCurrentUser } from "@/lib/api"

export const currentUserKey = ["current-user"] as const

// S6-05's route guard (AppShell in App.tsx) is the primary reader — it's
// what decides "does a valid session exist" once, on load, rather than
// inferring auth state from whichever page-specific query happens to run
// first. retry: false is deliberate: a 401 here means "not logged in,"
// not "transient failure" — retrying would just delay the redirect for
// no benefit. Any error (401 or otherwise) is treated as "no valid
// session" by the guard — there's no other failure mode worth
// distinguishing for a route guard's purposes.
export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserKey,
    queryFn: getCurrentUser,
    retry: false,
    // A 401 is an expected, common result (every logged-out visit), not
    // an application error — don't let react-query's default console
    // logging treat it as one.
    throwOnError: false,
  })
}
