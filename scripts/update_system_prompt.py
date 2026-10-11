"""Re-pushes a freshly-dated system prompt to an already-created assistant.

Use this instead of re-running create_assistant.py (which would create a
duplicate assistant) whenever the prompt needs refreshing -- most
importantly, every time "today" changes, since the prompt bakes in the
current date (see app/assistant_prompt.py).

Usage:
    python scripts/update_system_prompt.py
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.assistant_prompt import build_system_prompt  # noqa: E402
from app.config import settings  # noqa: E402

VAPI_API_BASE = "https://api.vapi.ai"


def main():
    if not settings.vapi_api_key:
        raise SystemExit("VAPI_API_KEY is not set in .env")

    assistant_id = input("Assistant ID to update: ").strip()
    if not assistant_id:
        raise SystemExit("An assistant ID is required.")

    headers = {"Authorization": f"Bearer {settings.vapi_api_key}", "Content-Type": "application/json"}
    prompt = build_system_prompt()

    with httpx.Client(timeout=30.0) as client:
        # Fetch the current model config first so we don't drop toolIds --
        # PATCH /assistant replaces the whole `model` object, not just the
        # fields you send.
        response = client.get(f"{VAPI_API_BASE}/assistant/{assistant_id}", headers=headers)
        response.raise_for_status()
        current_model = response.json()["model"]

        updated_model = {**current_model, "messages": [{"role": "system", "content": prompt}]}
        response = client.patch(
            f"{VAPI_API_BASE}/assistant/{assistant_id}", json={"model": updated_model}, headers=headers
        )
        response.raise_for_status()
        print("System prompt updated with today's date.")
        print("---")
        print(prompt)


if __name__ == "__main__":
    main()
