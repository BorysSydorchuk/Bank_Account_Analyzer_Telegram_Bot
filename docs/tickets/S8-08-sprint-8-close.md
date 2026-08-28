Status: in-progress

================================================================
TICKET S8-08 — Sprint 8 Close
================================================================

WHAT TO BUILD:
No new features. Full production verification and
documentation accuracy, same discipline as every prior sprint
close — this one closes the sprint that made real multi-bank
support and real beta access genuinely possible for the first
time.

ITEMS:

1. Full regression sweep against production, with BOTH banks
   and the full beta-access path:
   - KBC connection/sync/categorization/insights
   - ING connection/sync/categorization/insights
   - Registration gated by invite (both register and Google
     sign-in paths)
   - Email verification, password reset
   - Feedback channel
   - Usage guardrails (confirm caps still enforce correctly)
   - Chat, budgets, categories, manual editing — the full
     Sprint 1-7 surface, unchanged by this sprint but worth
     confirming nothing regressed

2. ARCHITECTURE.md full accuracy pass:
   - Multi-bank model (composite-key sessions, bank picker)
   - Usage guardrails
   - Beta invite gating
   - Resend email infrastructure (replacing SES references
     that are now historical, not current)
   - Public route enumeration, current as of this sprint

3. Security spot-check:
   - Confirm the invite-gating can't be bypassed (direct API
     call attempting registration without a valid invite)
   - Confirm usage caps hold under the same real-evidence
     standard as S8-04's original test
   - Re-confirm S6-07's original IDOR sweep still holds with
     two banks' worth of data now in the system

4. Ledger final state:
   - Zero stale entries
   - The users.email case-sensitivity bug (S8-06) — still
     genuinely deferred, re-dated if unchanged, or closed if
     someone picked it up
   - Confirm no entry was silently dropped the way the SES
     entry almost was in S8-05 — a full read-through, not a
     grep for keywords

5. Sprint 8 backlog sweep:
   - Confirm every ticket's real scope (including the S8-05
     insertion and renumbering) is accounted for
   - Carry forward explicitly: any beta users actually
     recruited and invited by this point, or note that this
     remains open and needs Borys's attention before Sprint 9

ACCEPTANCE CRITERIA:
- Full production regression passes, both banks, real evidence
  throughout
- ARCHITECTURE.md accurate
- Security spot-check passes
- Ledger current, full read-through confirmed (not just grep)
- No console errors on any page
- Sprint 8 complete pending PM confirmation

WHEN DONE:
- Production regression results, per surface, both banks
- ARCHITECTURE.md accuracy confirmation
- Security spot-check results
- Ledger state, explicitly confirmed via full read-through
- Beta user recruitment status — how many real people have
  actually been invited so far, if any
- Sprint 8 complete pending PM confirmation
