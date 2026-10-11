# Voice Agent + Calendar + CRM Demo

A small, CRM-agnostic reference implementation of the pattern most "integrate an AI
voice agent with our CRM and Google Calendar" jobs ask for:

```
Phone call -> Vapi (speech + LLM) -> webhook -> this FastAPI app -> Google Calendar
                                                                  -> generic CRM webhook
```

The voice agent (Vapi, using OpenAI as its model) never talks to Calendar or the CRM
directly. It calls three tools -- `check_availability`, `book_appointment`,
`create_lead` -- and this app is what actually does the work and answers back with a
sentence the agent can speak to the caller. Swapping Vapi for Retell, or the generic
webhook for a specific HubSpot/Zoho/Salesforce/GoHighLevel endpoint, doesn't change
anything else.

## Stack

- **FastAPI** -- webhook receiver (`app/main.py`)
- **Vapi** -- speech-to-text, LLM (OpenAI `gpt-4o`), text-to-speech, call handling
- **Google Calendar API** -- availability check + event creation (`app/calendar_service.py`)
- **Generic HTTP webhook** -- stands in for "the CRM" (`app/crm_service.py`)
- **Docker** -- `Dockerfile` / `docker-compose.yml`

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
.venv/Scripts/activate   # .venv/bin/activate on Linux/Mac
pip install -r requirements-dev.txt
cp .env.example .env
```

### 2. Vapi account (do this yourself -- sign-up isn't something this code does for you)

1. Create a free account at [vapi.ai](https://vapi.ai) and get an API key from the dashboard.
2. Put it in `.env` as `VAPI_API_KEY`.
3. (Optional but recommended) set a `VAPI_WEBHOOK_SECRET` in `.env` -- the same value also
   needs to be set as `server.secret` when you create the tools (see step 5), so Vapi
   sends it back on every webhook call for `main.py` to check.

### 3. OpenAI

The Vapi assistant uses OpenAI (`gpt-4o`) as its model. Create a key at
[platform.openai.com](https://platform.openai.com/api-keys) and put it in `.env` as
`OPENAI_API_KEY` -- Vapi needs this configured on your Vapi account (Settings -> Provider
Keys), not read directly by this app.

### 4. Google Calendar (OAuth, one-time local consent)

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and
   enable the **Google Calendar API**.
2. Create an OAuth client ID of type **Desktop app**, download its JSON, save it as
   `credentials/credentials.json`.
3. Run the one-time consent flow against your own Google account:
   ```bash
   python scripts/google_oauth_setup.py
   ```
   A browser window opens asking you to log in and approve access -- this writes a
   refresh token to `credentials/token.json`. Nothing here touches any account but your
   own, and it only needs to run once.

### 5. Expose the webhook and wire up the assistant

Locally, Vapi needs a public URL to call. Use a tunnel while developing:

```bash
uvicorn app.main:app --reload
ngrok http 8000   # note the https URL it prints
```

Then create the tools + assistant on Vapi:

```bash
python scripts/create_assistant.py
# paste the ngrok https URL + /webhook/vapi when prompted
```

Attach a phone number to the created assistant in the Vapi dashboard (Vapi can provision
a free test number) to start taking calls.

**Re-running after a restart:** ngrok's free tier hands out a new `https` URL every time
the tunnel restarts. Re-running `create_assistant.py` with the new URL would create a
*second* set of tools and assistant rather than updating the first. Use
`scripts/update_tool_urls.py` instead -- it finds the existing tools by name and PATCHes
their `server.url` in place.

### 6. Point at a real CRM (or leave it as a test sink)

Set `CRM_WEBHOOK_URL` in `.env` to:
- a real CRM's inbound webhook (a HubSpot workflow webhook trigger, a Zoho webhook
  action, a GoHighLevel webhook trigger, or a custom endpoint), or
- `https://webhook.site/<your-id>` while testing, to see the payloads land without a
  real CRM.

**Testing with webhook.site:**

1. Open [webhook.site](https://webhook.site) -- it immediately generates a unique URL
   like `https://webhook.site/e2dac0cb-3412-49de-ad5e-61354d5f5b2b`. Leave that tab open;
   every request to that URL shows up there live.
2. Put it in `.env` as `CRM_WEBHOOK_URL`.
3. **Restart the app** -- settings are only read from `.env` once, at process startup.
   `uvicorn --reload` watches your code for changes but not `.env`, so a `.env` edit
   needs a manual restart (Ctrl+C, re-run) to take effect, not just a save.
4. Trigger a tool call. Either call the assistant for real, or skip straight to the
   webhook without needing a live call:
   ```bash
   curl -X POST http://127.0.0.1:8000/webhook/vapi -H "Content-Type: application/json" -d '{
     "message": {
       "type": "tool-calls",
       "toolCalls": [{
         "id": "test_call_1",
         "function": {
           "name": "create_lead",
           "arguments": {"name": "Test Caller", "phone": "+37060000000", "notes": "Testing CRM webhook delivery"}
         }
       }]
     }
   }'
   ```
5. Check the webhook.site tab -- a POST should land within a second, with a body like:
   ```json
   {
     "name": "Test Caller",
     "phone": "+37060000000",
     "email": null,
     "notes": "Testing CRM webhook delivery",
     "source": "voice_agent",
     "appointment": null
   }
   ```
   For a `book_appointment` call instead of `create_lead`, `appointment` is populated
   with the real Google Calendar event's `event_id`, `html_link`, `start`, and `end`.

This confirms the delivery mechanism works end to end without needing a real CRM
account yet -- swap `CRM_WEBHOOK_URL` for the client's actual CRM webhook when you have
one, nothing else changes.

## Running

```bash
uvicorn app.main:app --reload        # local
# or
docker compose up --build            # containerized
```

`GET /health` for a liveness check. `POST /webhook/vapi` is what Vapi calls.

## Testing

```bash
pytest
```

Unit tests mock `calendar_service` and `crm_service`, so they run without real Vapi,
Google, or CRM credentials -- they verify the webhook routing and response formatting
(the part this repo owns), not the third-party APIs themselves.

To test the full live workflow end-to-end, call the Vapi assistant's phone number and:
1. Ask to book an appointment for a time you know is free -> confirms, appears on your
   Google Calendar, and the payload lands at `CRM_WEBHOOK_URL`.
2. Ask for a time that's already booked -> hear the alternative slot offered.
3. Decline to book and just leave your details -> `create_lead` fires instead.

You don't have to make a real call to check the CRM delivery path specifically -- the
`curl` command in the webhook.site section above hits `/webhook/vapi` directly with a
synthetic tool-call payload and exercises the exact same code the real call would.

## A bug this testing actually caught

A live test call booked an appointment that the assistant confirmed out loud, the
webhook returned `200 OK`, and nothing was logged as an error -- but the event never
showed up on the calendar, not even searching a 5-year window. Root cause: the system
prompt never told the model what "today" is, so its calculation of "tomorrow at 2pm"
could land on a date a year or more off while still being a perfectly valid ISO
datetime -- the kind of failure that produces no exception and no error log, just a
booking that silently goes to the wrong (or no findable) day.

Fixed in `app/assistant_prompt.py`: the system prompt now bakes in the actual current
date and timezone every time it's (re)built, and explicitly instructs the model to
compute relative dates from that stated date rather than guessing. `app/vapi_webhook.py`
also now logs every parsed date, with a loud warning if it's more than a year from now,
so this class of bug is visible in the logs immediately rather than silently vanishing.

Because the prompt bakes in "today," it goes stale -- re-run
`scripts/update_system_prompt.py` (updates the existing assistant in place, no
duplicate) periodically, or before a demo, so it isn't still saying yesterday's date.

## Notes on adapting this for a real client

- **Swap the voice platform**: Retell AI's tool-call webhook shape is similar (function
  name + arguments in, a result string out) -- `app/vapi_webhook.py` is the only file
  that would need a new parser for Retell's exact payload shape.
- **Swap the CRM**: `app/crm_service.py` posts a generic JSON payload. For a client on
  HubSpot/Zoho/Salesforce/GoHighLevel specifically, replace the generic POST with that
  CRM's actual API client (OAuth app, contact/lead endpoint) -- same call site, same
  contract with the rest of the app.
- **Multi-business reuse**: if this needs to serve more than one business (as
  Bussy'Note's SMS follow-up feature does per-organization), `GOOGLE_CALENDAR_ID`,
  `CRM_WEBHOOK_URL`, and the Vapi assistant/tool IDs would all need to move from global
  settings to a per-tenant lookup, the same shape as `Organization.twilio_from_number`.
