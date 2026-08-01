"""FastAPI web layer — sits alongside the existing kbc_analyzer CLI/bot package.

Everything under kbc_analyzer/ (Enable Banking client, Gemini analysis, Rich/Telegram
output) is reused as-is by importing from it. This package only adds the HTTP surface:
routers, request/response models, and the Postgres-backed persistence layer that
replaces the SQLite cache for the web app.
"""