"""Re-point the existing Vapi tools at a new webhook URL.

ngrok's free tier hands out a new https URL every time the tunnel restarts,
so re-running create_assistant.py after that would just create duplicate
tools/assistants. This finds the tools created by create_assistant.py by
name and PATCHes their server.url in place instead.

Usage:
    python scripts/update_tool_urls.py
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

VAPI_API_BASE = "https://api.vapi.ai"
TOOL_NAMES = {"check_availability", "book_appointment", "create_lead"}


def main():
    if not settings.vapi_api_key:
        raise SystemExit("VAPI_API_KEY is not set in .env")

    server_url = input("New public webhook URL for /webhook/vapi (e.g. an ngrok https URL): ").strip()
    if not server_url:
        raise SystemExit("A server URL is required.")

    headers = {"Authorization": f"Bearer {settings.vapi_api_key}", "Content-Type": "application/json"}

    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{VAPI_API_BASE}/tool", headers=headers)
        response.raise_for_status()
        tools = response.json()

        matched = [t for t in tools if t.get("function", {}).get("name") in TOOL_NAMES]
        if not matched:
            raise SystemExit("No matching tools found -- run scripts/create_assistant.py first.")

        for tool in matched:
            tool_id = tool["id"]
            name = tool["function"]["name"]
            response = client.patch(
                f"{VAPI_API_BASE}/tool/{tool_id}", json={"server": {"url": server_url}}, headers=headers
            )
            response.raise_for_status()
            print(f"Updated '{name}' ({tool_id}) -> {server_url}")


if __name__ == "__main__":
    main()
