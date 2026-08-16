Status: in-progress
Source: issued directly in Claude Code session, 2026-08-17

---

================================================================
TICKET S4-07 — AI Chat: Frontend  (reissued 2026-08-17,
                 prior scope addition void per S4-06 bounce)
================================================================

ROUTE: /chat — add "Chat" to sidebar between Dashboard
and Transactions.

LAYOUT:
  Message thread (scrollable, flex-grow):
    - User: right-aligned, primary blue bubble, white text
    - Assistant: left-aligned white card, border token,
      markdown rendered via react-markdown
    - Timestamps (HH:MM); blinking cursor while streaming;
      auto-scroll following tokens
  Input area (fixed bottom):
    - Multiline textarea, "Ask about your spending...",
      Enter sends / Shift+Enter newline
    - Send button (primary, arrow icon)
    - Disabled while streaming; 500-char limit with
      counter shown past 400

EMPTY STATE:
  "Chat with your finances" heading, subtitle, and 4
  suggestion chips that pre-fill and send:
    "How much did I spend this month?"
    "What's my biggest expense category?"
    "Am I within my budgets?"
    "Compare this month to last month"

SESSION: history in React state only; navigating away
clears it; "Clear conversation" button top-right.

STREAMING CONSUMPTION:
  fetch + response.body.getReader() (POST body needed —
  EventSource is GET-only). Parse SSE frames, append
  tokens.

ERRORS:
  Mid-stream failure → keep partial text + "Response
  interrupted — please try again" marker.
  No API key configured → toast directing to Settings.

ACCEPTANCE CRITERIA:
- Empty state + chips work
- Token-by-token rendering visible
- Multi-turn works; markdown renders (test with a
  question returning a list)
- Input disabled during streaming; auto-scroll correct
- Clear conversation works
- react-markdown added to dependencies (it is NOT yet
  installed — verify, don't assume)

WHEN DONE:
- Screenshots: empty state; mid-stream if capturable;
  a multi-turn conversation
- Markdown rendering confirmed
- Explain: why fetch + ReadableStream instead of
  EventSource?
- Do not start S4-08 until confirmed
