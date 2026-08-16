Status: delivered
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

---

## Delivery notes (Codee)

New files: `hooks/useChatSession.ts` (owns message state + SSE plumbing),
`lib/api.ts`'s `streamChat()` (fetch + `getReader()` SSE parser, returns an
abort function), `components/chat/{ChatEmptyState,MessageThread,
MessageBubble,ChatInput}.tsx`, `pages/ChatPage.tsx`. `react-markdown@10.1.0`
installed via `docker compose exec frontend npm install react-markdown` (it
was genuinely absent, confirmed before installing) — landed in both
`package.json` and the container's `node_modules` (a named Docker volume,
not host-mounted, so installing from the host wouldn't have reached the
running container).

Live-tested in a real browser (Chrome via claude-in-chrome) against the
real 331-transaction dataset, Docker stack up: empty state + all 4
suggestion chips (one clicked live, pre-filled and sent immediately);
token-by-token streaming (captured the blinking-cursor pre-token frame and
a mid-render frame); a 4-exchange conversation building correctly on prior
turns, including the assistant honestly declining a full month-over-month
comparison it didn't have data for rather than inventing one; markdown
bold/italic/bulleted-list rendering; input + send button disabled while
streaming; the 400-char counter threshold (appears at 401, reads "410/500")
and the 500-char hard cap (stops typing, counter turns red at "500/500");
Enter-to-send vs Shift+Enter-newline; Clear conversation (returns to empty
state). `tsc -b` and `oxlint` both pass clean, zero new warnings.

Two error paths — the "no API key" toast and the mid-stream "Response
interrupted" marker — were code-reviewed but not live-triggered (would
require destructively clearing Borys's real Gemini key, or killing the
connection mid-stream); logged in `docs/verification_debt.md`.

KEY DECISIONS:
- `fetch` + `response.body.getReader()` instead of `EventSource`:
  `EventSource` only supports GET requests with no custom body, and this
  endpoint needs a POST body carrying `{message, history}`. There's no way
  to send that via `EventSource` at all — this wasn't a preference between
  two working options, the ticket's own STREAMING CONSUMPTION section
  already specifies this.
- `useChatSession` is a plain hook (`useState`/`useCallback`), not a
  TanStack Query mutation — nothing here is cacheable (each stream is a
  one-shot side effect that mutates local message state token-by-token),
  and React Query's mutation lifecycle doesn't model "keep appending to a
  value over dozens of async callbacks" any more cleanly than plain state
  would.
- Belgian-locale amounts (`€ 1.234,56`) came through correctly in the
  assistant's replies because the backend already formats them that way in
  the context it sends — no frontend-side amount formatting was needed for
  chat text itself (unlike the rest of the app's `lib/format.ts`, which
  formats numbers the frontend renders directly, not text an LLM already
  wrote).

WATCH OUT FOR:
- `npm install` surfaced 2 pre-existing transitive vulnerabilities (1
  moderate in `hono`, 1 high in `nanoid`) unrelated to `react-markdown`
  itself — not fixed here (`npm audit fix` could shift unrelated dependency
  versions); flagging for a dependency-hygiene pass.
- Auto-scroll (`MessageThread`'s `scrollIntoView` effect) is implemented
  and runs on every message-array change, but wasn't stress-tested with
  enough content to actually force scrolling in this session — the real
  conversations tested fit within the viewport.

WHEN DONE — answered:
- Screenshots: captured empty state, a pre-token streaming frame, a
  mid-render frame, and multiple multi-turn exchanges (see this session's
  browser-tool output; not saved to the repo, per no-screenshot-files
  convention elsewhere in this project).
- Markdown rendering confirmed: bold merchant/amount, italic parenthetical
  detail, and a 7-item bulleted category breakdown all rendered correctly.
- Why fetch + ReadableStream instead of EventSource: EventSource is
  GET-only and cannot carry the POST body (`message` + `history`) this
  endpoint requires — not optional given the ticket's own request shape.
