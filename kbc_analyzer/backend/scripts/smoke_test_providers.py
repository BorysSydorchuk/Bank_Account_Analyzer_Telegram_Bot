"""S2-04 smoke test: instantiate both LLM providers directly (no DB/settings
involved — that's the registry's job, tested separately) and confirm complete()
returns a real string from each.
Usage: python -m scripts.smoke_test_providers  (run from /backend — needs -m so
/app is on sys.path for the `from app.agents...` import, same reason main.py's
own CMD uses `python -m uvicorn` instead of a bare script)
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from app.agents.providers.claude import ClaudeProvider
from app.agents.providers.gemini import GeminiProvider


async def main() -> None:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        gemini = GeminiProvider(gemini_key)
        result = await gemini.complete("Say hello", "Say hello")
        print(f"[gemini] OK — {result!r}")
    else:
        print("[gemini] SKIPPED — GEMINI_API_KEY not set in .env")

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        claude = ClaudeProvider(anthropic_key)
        result = await claude.complete("Say hello", "Say hello")
        print(f"[claude] OK — {result!r}")
    else:
        print("[claude] SKIPPED — ANTHROPIC_API_KEY not set in .env")


if __name__ == "__main__":
    asyncio.run(main())
