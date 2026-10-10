"""Google Calendar availability check + event creation.

Uses a one-time OAuth user-consent flow (see scripts/google_oauth_setup.py)
rather than a service account: a personal/workspace Gmail calendar isn't
reachable by a bare service account without domain-wide delegation, which
needs a Google Workspace admin. The OAuth flow works against any Google
account, which fits a demo/small-business setting better.
"""

import datetime as dt
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarNotConfigured(Exception):
    """Raised when the OAuth token hasn't been generated yet (run scripts/google_oauth_setup.py)."""


def _load_credentials():
    if not os.path.exists(settings.google_token_file):
        raise CalendarNotConfigured(
            f"{settings.google_token_file} not found. Run scripts/google_oauth_setup.py first."
        )

    creds = Credentials.from_authorized_user_file(settings.google_token_file, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(settings.google_token_file, "w") as f:
            f.write(creds.to_json())
    return creds


def _service():
    return build("calendar", "v3", credentials=_load_credentials())


def check_availability(start: dt.datetime, end: dt.datetime) -> bool:
    """Return True if there is no existing event overlapping [start, end)."""
    service = _service()
    result = (
        service.freebusy()
        .query(
            body={
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "items": [{"id": settings.google_calendar_id}],
            }
        )
        .execute()
    )
    busy_slots = result["calendars"][settings.google_calendar_id]["busy"]
    return len(busy_slots) == 0


def find_next_available_slot(
    earliest: dt.datetime, duration_minutes: int, search_days: int = 7
) -> dt.datetime | None:
    """Walk forward in `duration_minutes` steps during business hours (9-17) to find a free slot."""
    slot = earliest
    deadline = earliest + dt.timedelta(days=search_days)

    while slot < deadline:
        if 9 <= slot.hour < 17:
            slot_end = slot + dt.timedelta(minutes=duration_minutes)
            if check_availability(slot, slot_end):
                return slot
            slot = slot + dt.timedelta(minutes=duration_minutes)
        else:
            slot = slot.replace(hour=9, minute=0, second=0) + dt.timedelta(days=1)

    return None


def book_appointment(
    start: dt.datetime, duration_minutes: int, summary: str, description: str, attendee_email: str | None
) -> dict:
    """Create a calendar event and return {event_id, html_link, start, end}."""
    service = _service()
    end = start + dt.timedelta(minutes=duration_minutes)

    event_body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": settings.business_timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": settings.business_timezone},
    }
    if attendee_email:
        event_body["attendees"] = [{"email": attendee_email}]

    created = service.events().insert(
        calendarId=settings.google_calendar_id, body=event_body, sendUpdates="all"
    ).execute()

    return {
        "event_id": created["id"],
        "html_link": created.get("htmlLink"),
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
