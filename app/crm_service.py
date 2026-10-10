"""Generic outbound webhook to 'the CRM'.

Deliberately CRM-agnostic: this project's point is to show the voice-agent
<-> calendar <-> CRM wiring pattern, not a specific vendor's SDK. Point
CRM_WEBHOOK_URL at a real CRM's inbound webhook (HubSpot workflow webhook
trigger, Zoho webhook action, a GoHighLevel webhook trigger, or a custom
endpoint like crm.tasks.send_sms_followup's app) to make this concrete for
a given client; this module doesn't change either way.
"""

import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)


class CRMWebhookNotConfigured(Exception):
    """Raised when CRM_WEBHOOK_URL isn't set."""


async def push_contact(name: str, phone: str, email: str | None, notes: str, appointment: dict | None) -> None:
    """POST a contact/lead payload to the configured CRM webhook.

    Logs and returns rather than raising on delivery failure -- a failed
    CRM sync shouldn't fail the phone call or the calendar booking that
    already succeeded; it should be retried/alerted separately.
    """
    if not settings.crm_webhook_url:
        raise CRMWebhookNotConfigured("CRM_WEBHOOK_URL nenustatytas aplinkos kintamuosiuose.")

    payload = {
        "name": name,
        "phone": phone,
        "email": email,
        "notes": notes,
        "source": "voice_agent",
        "appointment": appointment,
    }
    headers = {}
    if settings.crm_webhook_auth_header:
        headers["Authorization"] = settings.crm_webhook_auth_header

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.crm_webhook_url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info("CRM webhook delivered for %s (%s)", name, phone)
    except httpx.HTTPError as exc:
        logger.error("CRM webhook delivery failed for %s (%s): %s", name, phone, exc)
