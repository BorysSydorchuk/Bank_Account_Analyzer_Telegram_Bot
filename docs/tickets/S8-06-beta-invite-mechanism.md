Status: in-progress

================================================================
TICKET S8-06 — Beta Invite Mechanism
================================================================

PRE-CHECK: before building anything, confirm the full
registration → verification round-trip genuinely works end to
end for a person who is neither Borys nor liyaberry27@gmail.com
— a real, fresh third-party test if possible, since that's the
actual proof S8-05's fix achieves what the sprint needs. If a
real third person isn't available, at minimum a genuinely fresh
address never previously touched by this project.

WHAT TO BUILD:
- A simple way for Borys to grant beta access to specific real
  people without opening registration to the general public —
  an invite-code system, an admin-granted allowlist, or
  equivalent (your call, justify the choice)
- Should be simple to operate manually (Borys adding a handful
  of people), not an over-engineered general-purpose invite
  system — this is for 10-20 people, not scale

ACCEPTANCE CRITERIA:
- Borys can grant access to a specific real email/person
  without public registration being open to everyone
- Tested with a real invite granted and used end-to-end
- Pre-check's fresh third-party registration confirmed working

WHEN DONE:
- Real evidence of the invite mechanism working end-to-end
- Pre-check registration proof
- Do not start S8-07 until confirmed
