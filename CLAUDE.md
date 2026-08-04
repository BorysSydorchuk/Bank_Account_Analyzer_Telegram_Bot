================================================================
CODEE HARDCODED REQUIREMENTS
KBC Personal Finance Analyzer
================================================================
 
These rules apply to EVERY response, EVERY ticket, EVERY
session. They are not optional and do not need to be repeated
in individual tickets — they are always active.
 
================================================================
PROMPT 1 — EXPLANATION STANDARD
================================================================
 
After completing any piece of work, explain what you built
using the following standard:
 
WHO YOU ARE EXPLAINING TO:
Borys is a backend-leaning intermediate developer. He knows
Python, FastAPI, Docker, PostgreSQL, REST APIs, and Git at
a working level. He has built real projects with these. He
has growing but not yet deep knowledge of React, TypeScript,
SQLAlchemy, Alembic, and security patterns.
 
He does NOT need:
- Basic syntax explained ("this is a for loop")
- Definitions of general programming concepts he already knows
- Step-by-step breakdowns of boilerplate
 
He DOES need:
- The "why this approach and not another" always explained
- Non-obvious framework behavior called out explicitly
  (e.g. why enabled:false in React Query, why Alembic stamp
  vs run, why Fernet over bcrypt for this use case)
- When you made a choice between two valid options, say what
  the other option was and why you picked this one
- When something could go wrong later, flag it proactively
- Security or architectural decisions explained with consequences
  ("if we didn't do X, then Y would happen")
- New concepts (things outside his core stack) introduced with
  a one-sentence mental model before the technical detail
 
FORMAT FOR EXPLANATIONS:
Do not write walls of text. Use this structure after each ticket:
 
  WHAT I BUILT
  One paragraph, plain English, what exists now that didn't before.
 
  KEY DECISIONS
  Bullet list. Each bullet: decision made → why → what the
  alternative was. Maximum 5 bullets. Only include decisions
  that are non-obvious or had real tradeoffs.
 
  WATCH OUT FOR
  Bullet list of things that could bite us later — known
  limitations, expiry dates, edge cases, technical debt
  consciously taken on. If nothing, say "Nothing flagged."
 
  HOW IT CONNECTS
  One short paragraph: how this ticket's code connects to
  what came before and what comes after it in the sprint.
 
================================================================
PROMPT 2 — ARCHITECTURE & CODE QUALITY STANDARD
================================================================
 
Every piece of code you write must meet these standards.
A senior engineer should be able to open any file and
understand it within 2 minutes.
 
STRUCTURE:
- One responsibility per file. A file that fetches data
  does not also format it. A file that defines a route
  does not also contain business logic.
- Follow the existing separation: routes in main.py,
  database queries in crud.py, business logic in services/,
  agents in agents/. Do not collapse these into each other
  for convenience.
- New modules go in a predictable location. If it is not
  obvious where a new file belongs, create a new folder
  with a clear name rather than putting it somewhere
  approximate.
 
NAMING:
- Functions named for what they return or what they do,
  not how they do it. get_transactions() not
  fetch_and_process_transaction_data().
- Variables named for what they contain.
  uncategorized_transactions not data or items or result.
- No abbreviations except universally understood ones
  (id, url, api, db). Not tx, not txn, not trx.
 
COMMENTS:
- Every function has a docstring. One sentence minimum.
  For complex functions: what it takes, what it returns,
  what it raises.
- Inline comments only for non-obvious logic.
  If the code is readable, do not comment it.
  If you feel the need to comment obvious code, rewrite
  the code to be clearer instead.
- Every TODO left in code must include: what needs doing,
  why it was deferred, which sprint it belongs to.
  Format: # TODO(Sprint N): description — reason deferred
 
ERRORS:
- Never let an exception surface as a raw Python traceback
  to the API consumer. Every exception is caught at the
  appropriate layer and returned as a structured response.
- Error messages must tell the user what happened AND
  what to do about it. "Database unavailable. Please try
  again shortly." not "connection refused."
- Log errors with enough context to debug them:
  which endpoint, which user action, what the exception was.
 
ENVIRONMENT:
- No hardcoded values that belong in configuration.
  Strings, URLs, thresholds, model names — all go in .env
  or as named constants at the top of the file.
- No secrets ever in code, even in comments.
 
FRONTEND SPECIFIC:
- Components do one thing. A component that fetches data,
  formats it, and renders three different layouts is three
  components.
- Props are typed explicitly. No prop: any.
- useEffect dependencies are always complete and correct.
  If a linter complains about a missing dependency, fix
  the code, do not silence the linter.
- The design token system from index.css is always used.
  No hardcoded hex values, no inline styles for colors.
 
GIT:
- One commit per ticket. Message format:
  feat: S2-XX short description
- If a bug fix is needed mid-ticket, it goes in the same
  commit unless it touches an entirely different concern.
- Never commit .env, eb_session.json, or __pycache__.
 
================================================================
PROMPT 3 — SECURITY STANDARD
================================================================
 
This product handles real bank data and will eventually have
real users. Security is not optional and is not deferred to
a "security sprint."
 
NEVER DO:
- Log transaction amounts, descriptions, or any financial
  data at INFO level. Use DEBUG level only, which is off
  in production.
- Store API keys or secrets in plaintext anywhere except
  the .env file (which is gitignored).
- Return stack traces or internal error details to the
  API consumer.
- Trust user-supplied input without validation.
  All inputs are validated before touching the database.
- Use string concatenation to build SQL queries.
  SQLAlchemy ORM or parameterized queries only.
 
ALWAYS DO:
- Validate date ranges on the backend. date_from must be
  before date_to. Maximum range: 365 days. Return 400
  with a clear message if violated.
- Sanitize text inputs (search, description fields) before
  use in queries.
- Set CORS to accept requests only from the known frontend
  origin (FRONTEND_ORIGIN env var), never wildcard (*) in
  production mode.
- When adding authentication in Sprint 5, every database
  query must be scoped to the authenticated user's ID.
  No query should ever be able to return another user's data.
 
FOR NOW (pre-auth sprints):
The app is single-user and runs locally, so some of these
rules are precautionary rather than immediately critical.
However, write the code as if auth is coming — never hard-
code assumptions that there is only one user.
 
================================================================
PROMPT 4 — TESTING STANDARD
================================================================
 
You are not required to write full test suites for every
ticket. You ARE required to verify your work before saying
it is done.
 
FOR EVERY TICKET:
- Show the actual output of running your code against real
  data, not hypothetical expected output.
- For backend endpoints: show the real HTTP response from
  a real request (curl output or equivalent).
- For frontend components: show a real screenshot from
  the browser, not a description of what it looks like.
- For database changes: show the result of a query proving
  the schema or data is in the expected state.
 
FOR COMPLEX LOGIC (agents, auth flows, migrations):
- Write a smoke test that can be run with one command
  and proves the core behavior works.
- Document what you tested and what the result was in
  your WHEN DONE response.
 
WHAT "DONE" MEANS:
A ticket is not done when the code is written.
A ticket is done when:
1. The code is written
2. It has been tested against real data or real conditions
3. The WHEN DONE questions are answered with real outputs
4. The code is committed with the correct message
 
================================================================
PROMPT 5 — SCOPE DISCIPLINE
================================================================
 
You work on one ticket at a time. This rule is absolute.
 
NEVER:
- Start the next ticket before the current one is confirmed
  by Borys (he gets confirmation from the PM first).
- Add features or improvements that are not in the ticket
  because they seem like good ideas.
- Refactor code from previous tickets unless the current
  ticket explicitly requires it.
- Make changes to files outside the scope of the current
  ticket without flagging it first.
 
IF YOU NOTICE SOMETHING:
You may flag issues you notice in other parts of the code
during your work. Flagging is encouraged. Fixing without
permission is not.
 
Format for flagging:
  FLAGGED (out of scope):
  [What you noticed] in [file/component].
  [Why it might matter].
  [Suggested sprint to fix it].
 
This keeps the git history clean, keeps sprints predictable,
and gives Borys as CEO full control over what gets built
and when.
 
================================================================
PROMPT 6 — COMMUNICATION STANDARD
================================================================
 
Borys acts as CEO and bridge between you and the PM.
Treat every ticket as a professional handoff.
 
ALWAYS:
- Answer the WHEN DONE questions explicitly and in order.
  Do not skip questions. Do not give vague answers.
- Flag anything unexpected that happened during the build,
  even if you resolved it. Borys needs to know what was
  tricky so he can report it accurately to the PM.
- If a ticket requirement is ambiguous or technically
  impossible as written, say so immediately rather than
  making assumptions. Propose an alternative and wait
  for a decision before proceeding.
- End every completed ticket with:
  "Ready for [S2-0X] whenever you confirm this one."
 
NEVER:
- Say a ticket is done if any acceptance criterion is unmet.
- Start the next ticket speculatively while waiting for
  confirmation.
- Make a significant architectural decision without flagging
  it, even if you are confident it is correct.
 