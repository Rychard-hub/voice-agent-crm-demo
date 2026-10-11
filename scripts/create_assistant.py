"""Creates the three function tools and the Vapi assistant that uses them.

Schema verified against https://docs.vapi.ai/tools/custom-tools and
https://docs.vapi.ai/assistants/quickstart (fetched 2026-10-10). Vapi's API
has changed shape before -- re-check the live docs if this returns a
schema-validation error.

Usage:
    python scripts/create_assistant.py

Requires VAPI_API_KEY and a running, publicly reachable SERVER_URL (use
ngrok while testing locally: `ngrok http 8000`, then pass its https URL).
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.assistant_prompt import build_system_prompt  # noqa: E402
from app.config import settings  # noqa: E402

VAPI_API_BASE = "https://api.vapi.ai"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check whether a given date and time is free on the business calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "ISO date, e.g. 2026-10-15"},
                    "time": {"type": "string", "description": "24h time, e.g. 14:00"},
                },
                "required": ["date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment at a specific date and time for the caller.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "ISO date, e.g. 2026-10-15"},
                    "time": {"type": "string", "description": "24h time, e.g. 14:00"},
                    "name": {"type": "string", "description": "Caller's full name"},
                    "phone": {"type": "string", "description": "Caller's phone number"},
                    "email": {"type": "string", "description": "Caller's email, if given"},
                    "notes": {"type": "string", "description": "What the appointment is for"},
                },
                "required": ["date", "time", "name", "phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_lead",
            "description": "Log the caller's details for a follow-up when they don't want to book a specific time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Caller's full name"},
                    "phone": {"type": "string", "description": "Caller's phone number"},
                    "email": {"type": "string", "description": "Caller's email, if given"},
                    "notes": {"type": "string", "description": "What they called about"},
                },
                "required": ["name", "phone"],
            },
        },
    },
]


def main():
    if not settings.vapi_api_key:
        raise SystemExit("VAPI_API_KEY is not set in .env")

    server_url = input("Public webhook URL for /webhook/vapi (e.g. an ngrok https URL): ").strip()
    if not server_url:
        raise SystemExit("A server URL is required so Vapi can call your tools.")

    headers = {"Authorization": f"Bearer {settings.vapi_api_key}", "Content-Type": "application/json"}

    tool_ids = []
    with httpx.Client(timeout=30.0) as client:
        for tool in TOOLS:
            body = {**tool, "server": {"url": server_url}}
            response = client.post(f"{VAPI_API_BASE}/tool", json=body, headers=headers)
            response.raise_for_status()
            tool_id = response.json()["id"]
            tool_ids.append(tool_id)
            print(f"Created tool '{tool['function']['name']}' -> {tool_id}")

        assistant_body = {
            "name": "Booking Assistant Demo",
            "firstMessage": "Hi, thanks for calling! How can I help you today?",
            "model": {
                "provider": "openai",
                "model": "gpt-4o",
                "messages": [{"role": "system", "content": build_system_prompt()}],
                "toolIds": tool_ids,
            },
            "voice": {"provider": "vapi", "voiceId": "Elliot"},
            "transcriber": {"provider": "deepgram", "model": "nova-3", "language": "en"},
        }
        response = client.post(f"{VAPI_API_BASE}/assistant", json=assistant_body, headers=headers)
        response.raise_for_status()
        assistant = response.json()
        print(f"Created assistant '{assistant['name']}' -> {assistant['id']}")
        print("Attach a phone number to it in the Vapi dashboard to start taking calls.")


if __name__ == "__main__":
    main()
