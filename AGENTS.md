# AGENTS.md — Agentic Workflow for This Repository

This project is built by a coordinated set of AI agents
directed by a human product owner. This file defines who
does what, so any agent (or human) joining the project
understands the structure immediately.

## Roles

| Role | Runs in | Rulebook | Writes code? |
|---|---|---|---|
| CEO / Product Owner (Borys, human) | — | — | No |
| PM | Claude chat | (chat context) | No |
| Implementer ("Codee") | Claude Code | CLAUDE.md | Yes |
| Reviewer | Claude Code (separate session) | REVIEWER.md | Never |
| Tester (from Sprint 5) | Claude Code (separate session) | TESTER.md | Tests only |
| Security Auditor (Sprint 6, before auth ships) | Claude Code | (brief written per-audit by PM) | Never |

## The loop (per ticket)

1. PM writes the ticket with acceptance criteria → Borys
   carries it to Codee.
2. Codee's first action, before building anything: commit
   the ticket's text verbatim to
   docs/tickets/S4-XX-short-name.md with a `Status:
   in-progress` line at the top.
3. Codee verifies the ticket's premise against
   ARCHITECTURE.md and the running system, then implements,
   commits (one commit per ticket), and writes a delivery
   report (format in CLAUDE.md). The docs/tickets/ file's
   `Status:` line updates to `delivered` in the same commit
   (or a follow-up commit once live verification closes any
   deferred items), with delivery notes appended below the
   ticket text.
4. Reviewer independently reviews the DIFF against the
   ticket + rulebooks (procedure in REVIEWER.md) and issues
   PASS / PASS WITH NOTES / FAIL.
5. Borys takes both reports to the PM → PM gives the
   verdict → Borys confirms or bounces the ticket to Codee.
   On confirmation, the docs/tickets/ file's `Status:` line
   updates to `confirmed` (Codee's next ticket does this as
   a small housekeeping step, since confirmation itself
   happens outside Claude Code).
6. From Sprint 5: Tester adds/extends tests for the
   confirmed ticket and runs the full suite; RED blocks the
   next ticket.

## Coordination rules

- Agents coordinate through repo files, never through each
  other: CLAUDE.md (standards), ARCHITECTURE.md (current
  state), docs/verification_debt.md (deferred
  verifications), docs/tickets/ (every ticket issued, as
  Codee received it, with its live Status: and delivery
  notes — repo ground truth for what was actually asked
  for, independent of chat history), AGENTS.md (this file).
- One ticket at a time per implementer. Two implementer
  sessions may run in parallel ONLY on tickets the PM has
  explicitly marked independent (disjoint file trees).
  Never two agents writing in the same directory tree.
- The Reviewer and Tester never instruct Codee directly;
  all direction flows through Borys/PM.
- No agent performs destructive actions on real data or
  live credentials without Borys's explicit consent
  (CLAUDE.md verification rules).
- Ground truth for "what the system does" is
  ARCHITECTURE.md + the code, never an agent's memory or
  a chat transcript.
