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

### 6. Point at a real CRM (or leave it as a test sink)

Set `CRM_WEBHOOK_URL` in `.env` to:
- a real CRM's inbound webhook (a HubSpot workflow webhook trigger, a Zoho webhook
  action, a GoHighLevel webhook trigger, or a custom endpoint), or
- `https://webhook.site/<your-id>` while testing, to see the payloads land without a
  real CRM.

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
