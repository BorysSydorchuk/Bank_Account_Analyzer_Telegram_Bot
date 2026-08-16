Status: delivered
Source: sprint4_tickets_v2.txt (revised set)

---

# TICKET S4-06 — AI CHAT: BACKEND

BEFORE WRITING CODE (CLAUDE.md premise rule): verify against
the running system and ARCHITECTURE.md that the endpoints,
ports, and flows this ticket assumes are current. Flag any
mismatch before building.

WHAT TO BUILD:
A streaming chat endpoint answering questions grounded in
the user's real transaction data. Most architecturally
complex ticket of the sprint — design before code.

CHAT AGENT: backend/app/agents/chat.py

  class ChatAgent(BaseAgent):
    name = "chat"

    async def stream(
      self,
      message: str,
      history: list[dict],
      context: dict
    ) -> AsyncGenerator[str, None]:

FINANCIAL CONTEXT (fetched fresh per message, injected into
the system prompt, never into history):
  - Summary stats, last 90 days (total_spent,
    total_received, net, by_category)
  - Last 20 transactions (date, description, amount,
    category)
  - Active budgets with current status (the S4-05
    endpoints/service give you this)
  - Date range of available data

SYSTEM PROMPT:
  You are a personal finance assistant with access to the
  user's real bank transaction data. Answer concisely and
  specifically — always reference actual amounts, dates,
  and merchant names from the data.

  Today's date: {today}
  Data available from: {earliest_date} to {latest_date}

  SPENDING SUMMARY (last 90 days):
  {summary}

  RECENT TRANSACTIONS (last 20):
  {transactions}

  ACTIVE BUDGETS:
  {budgets}

  Rules:
  - If the answer requires data outside what's provided,
    say so — never invent transactions or amounts
  - Under 150 words unless the user asks for detail
  - Format amounts as € X,XXX.XX

STREAMING ENDPOINT:
  POST /api/chat
  Body: {"message": "...",
         "history": [{"role": "user"|"assistant",
                      "content": "..."}]}
  Response: SSE stream (text/event-stream) via FastAPI
  StreamingResponse.
  Events: data: {"token": "...", "done": false}
  Final:  data: {"token": "", "done": true,
                 "usage": {"input": N, "output": M}}

PROVIDER INTERFACE ADDITION:
  async def stream_complete(
    self, system: str, messages: list[dict]
  ) -> AsyncGenerator[str, None]
  Gemini: generate_content_async(..., stream=True), yield
  chunk text — verify the exact google-genai streaming API
  against the installed SDK version, don't assume.
  Claude: client.messages.stream() context manager, yield
  delta text. (Structural implementation; live verification
  goes to the verification-debt ledger until the key
  arrives.)

HISTORY: client-side entirely; backend stateless; max 20
messages, truncate oldest.

ACCEPTANCE CRITERIA:
- Tokens stream in real time (not one flush at the end)
- Context contains real data; "what was my biggest
  expense?" answer matches GET /api/statistics
- Multi-turn history works within a session
- Gemini live-verified; Claude structurally verified (+
  ledger entry)
- ARCHITECTURE.md data-flow section gains the chat flow
  in the same commit

WHEN DONE:
- A real ≥3-exchange conversation with specific amounts
- SSE frames visible (curl or network tab)
- Biggest-expense cross-check against GET /api/statistics
- Explain: why stateless backend + client-held history
  rather than DB-stored conversations?
- Do not start S4-07 until Borys confirms.

---

## Delivery notes (Codee)

Delivered across two commits:
- `6ae4585` — feat: S4-06 AI chat backend (implementation; Docker was down,
  so Gemini/Claude streaming were structurally verified only, logged in
  docs/verification_debt.md)
- `8aef752` — chore: S4-06 live-verify Gemini chat streaming, close
  Docker-blocked debt (Docker came back up; real 3-exchange conversation
  against the real 331-transaction dataset)

One deviation from the literal spec, called out at delivery time: amounts
are formatted in this app's established Belgian locale (`€ 1.234,56`)
rather than the ticket's literal example `€ X,XXX.XX`, for consistency with
the rest of the product.

One real, non-blocking limitation surfaced by live verification, not a bug:
the "last 20 transactions" context section can be a small slice of a much
larger summary window (293 transactions fell in the real 90-day window
tested) — a "what was my single biggest expense" question can miss rows
older than the visible 20. The assistant is instructed to say so rather
than guess, and did. See ARCHITECTURE.md's chat-flow note and
docs/verification_debt.md's CLOSED section for the full record.

Claude's stream_complete() remains structurally verified only — no
ANTHROPIC_API_KEY has ever been available (open item in
docs/verification_debt.md, same underlying gap as the Sprint 2 Claude
provider gap).

---

## AMENDMENT (2026-08, at S4-06 confirmation review)

Finding from live verification: the true 90-day biggest
expense (€800.00, 2026-07-27) fell outside the last-20-
transactions context window; the assistant correctly
declined to answer rather than hallucinate. Ruled a spec
gap in this ticket's context design, not an implementation
defect.

Resolution, folded into S4-07's scope:
Include statistics.summary.biggest_expense (last 90 days)
as its own labeled field in the chat context prompt, so
"biggest expense" questions are answerable. One field —
the 20-transaction window itself is unchanged. Update
ARCHITECTURE.md and close the corresponding
verification_debt.md note in the same commit.
