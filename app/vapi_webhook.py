"""Dispatches Vapi tool-calls to the calendar/CRM services and formats a
spoken-friendly result string for each, per Vapi's tool-calls webhook
contract: https://docs.vapi.ai/ (verify the exact shape against Vapi's
current docs -- Vapi's webhook payloads have changed before).
"""

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from . import calendar_service, crm_service
from .config import settings
from .schemas import ToolCall, ToolCallResult

logger = logging.getLogger(__name__)


def _parse_datetime(date_str: str, time_str: str) -> dt.datetime:
    tz = ZoneInfo(settings.business_timezone)
    return dt.datetime.fromisoformat(f"{date_str}T{time_str}").replace(tzinfo=tz)


async def _handle_check_availability(args: dict) -> str:
    start = _parse_datetime(args["date"], args["time"])
    end = start + dt.timedelta(minutes=settings.appointment_duration_minutes)

    try:
        if calendar_service.check_availability(start, end):
            return f"Yes, {start.strftime('%A %B %d at %H:%M')} is available."

        alternative = calendar_service.find_next_available_slot(
            end, settings.appointment_duration_minutes
        )
        if alternative:
            return (
                f"{start.strftime('%A %B %d at %H:%M')} is already booked. "
                f"The next available slot is {alternative.strftime('%A %B %d at %H:%M')}."
            )
        return f"{start.strftime('%A %B %d at %H:%M')} is already booked, and no slot opened up in the next week."
    except calendar_service.CalendarNotConfigured:
        logger.error("check_availability called but Google Calendar isn't configured")
        return "I'm sorry, I can't check the calendar right now. Someone will call you back to confirm a time."


async def _handle_book_appointment(args: dict) -> str:
    start = _parse_datetime(args["date"], args["time"])
    name = args.get("name", "the caller")
    phone = args.get("phone", "")
    email = args.get("email")
    notes = args.get("notes", "")

    try:
        if not calendar_service.check_availability(
            start, start + dt.timedelta(minutes=settings.appointment_duration_minutes)
        ):
            return f"Sorry, {start.strftime('%A %B %d at %H:%M')} just got booked. Could you pick another time?"

        appointment = calendar_service.book_appointment(
            start=start,
            duration_minutes=settings.appointment_duration_minutes,
            summary=f"Appointment with {name}",
            description=notes,
            attendee_email=email,
        )
    except calendar_service.CalendarNotConfigured:
        logger.error("book_appointment called but Google Calendar isn't configured")
        return "I'm sorry, I can't access the calendar right now. Someone will call you back to confirm a time."

    try:
        await crm_service.push_contact(
            name=name, phone=phone, email=email, notes=notes, appointment=appointment
        )
    except crm_service.CRMWebhookNotConfigured:
        logger.warning("Appointment booked but CRM_WEBHOOK_URL isn't set -- contact wasn't pushed to the CRM")

    return f"You're booked for {start.strftime('%A %B %d at %H:%M')}. A confirmation will be sent to you."


async def _handle_create_lead(args: dict) -> str:
    name = args.get("name", "the caller")
    phone = args.get("phone", "")
    email = args.get("email")
    notes = args.get("notes", "")

    try:
        await crm_service.push_contact(name=name, phone=phone, email=email, notes=notes, appointment=None)
        return "Thanks, I've logged your details and someone from the team will follow up with you."
    except crm_service.CRMWebhookNotConfigured:
        logger.error("create_lead called but CRM_WEBHOOK_URL isn't configured")
        return "Thanks for the information. Someone will follow up with you shortly."


_HANDLERS = {
    "check_availability": _handle_check_availability,
    "book_appointment": _handle_book_appointment,
    "create_lead": _handle_create_lead,
}


async def handle_tool_call(tool_call: ToolCall) -> ToolCallResult:
    handler = _HANDLERS.get(tool_call.function.name)
    if handler is None:
        result = f"Unknown tool: {tool_call.function.name}"
    else:
        try:
            result = await handler(tool_call.function.arguments)
        except Exception:
            logger.exception("Error handling tool call %s", tool_call.function.name)
            result = "Sorry, something went wrong on our end handling that."

    return ToolCallResult(toolCallId=tool_call.id, result=result)
