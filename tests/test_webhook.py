import datetime as dt
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def _tool_call_payload(name: str, arguments: dict, call_id: str = "call_1") -> dict:
    return {
        "message": {
            "type": "tool-calls",
            "toolCalls": [{"id": call_id, "function": {"name": name, "arguments": arguments}}],
        }
    }


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("app.calendar_service.check_availability", return_value=True)
def test_check_availability_when_free(mock_check):
    response = client.post(
        "/webhook/vapi", json=_tool_call_payload("check_availability", {"date": "2026-11-02", "time": "14:00"})
    )
    assert response.status_code == 200
    result = response.json()["results"][0]["result"]
    assert "available" in result.lower()
    assert mock_check.called


@patch("app.calendar_service.find_next_available_slot")
@patch("app.calendar_service.check_availability", return_value=False)
def test_check_availability_when_busy_offers_alternative(mock_check, mock_alt):
    mock_alt.return_value = dt.datetime(2026, 11, 2, 15, 0, tzinfo=dt.timezone.utc)
    response = client.post(
        "/webhook/vapi", json=_tool_call_payload("check_availability", {"date": "2026-11-02", "time": "14:00"})
    )
    result = response.json()["results"][0]["result"]
    assert "already booked" in result.lower()
    assert "15:00" in result


@patch("app.crm_service.push_contact", new_callable=AsyncMock)
@patch("app.calendar_service.book_appointment")
@patch("app.calendar_service.check_availability", return_value=True)
def test_book_appointment_success(mock_check, mock_book, mock_push):
    mock_book.return_value = {
        "event_id": "evt_1",
        "html_link": "https://calendar.google.com/evt_1",
        "start": "2026-11-02T14:00:00",
        "end": "2026-11-02T14:30:00",
    }
    payload = _tool_call_payload(
        "book_appointment",
        {"date": "2026-11-02", "time": "14:00", "name": "Jane Doe", "phone": "+15551234567"},
    )
    response = client.post("/webhook/vapi", json=payload)
    result = response.json()["results"][0]["result"]
    assert "you're booked" in result.lower()
    mock_book.assert_called_once()
    mock_push.assert_awaited_once()


@patch("app.calendar_service.check_availability", return_value=False)
def test_book_appointment_conflict(mock_check):
    payload = _tool_call_payload(
        "book_appointment",
        {"date": "2026-11-02", "time": "14:00", "name": "Jane Doe", "phone": "+15551234567"},
    )
    response = client.post("/webhook/vapi", json=payload)
    result = response.json()["results"][0]["result"]
    assert "just got booked" in result.lower()


@patch("app.crm_service.push_contact", new_callable=AsyncMock)
def test_create_lead(mock_push):
    payload = _tool_call_payload("create_lead", {"name": "Jane Doe", "phone": "+15551234567", "notes": "pricing question"})
    response = client.post("/webhook/vapi", json=payload)
    result = response.json()["results"][0]["result"]
    assert "logged" in result.lower()
    mock_push.assert_awaited_once()


def test_unknown_tool_returns_placeholder_without_erroring():
    response = client.post("/webhook/vapi", json=_tool_call_payload("delete_everything", {}))
    assert response.status_code == 200
    assert "unknown tool" in response.json()["results"][0]["result"].lower()


def test_non_tool_call_message_returns_empty_results():
    response = client.post("/webhook/vapi", json={"message": {"type": "status-update", "toolCalls": []}})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_webhook_rejects_wrong_secret():
    settings.vapi_webhook_secret = "expected-secret"
    try:
        response = client.post(
            "/webhook/vapi",
            json=_tool_call_payload("create_lead", {"name": "Jane", "phone": "123"}),
            headers={"x-vapi-secret": "wrong"},
        )
        assert response.status_code == 401
    finally:
        settings.vapi_webhook_secret = ""
