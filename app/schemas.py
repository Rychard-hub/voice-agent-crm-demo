from typing import Any

from pydantic import BaseModel


class ToolCallFunction(BaseModel):
    name: str
    arguments: dict[str, Any]


class ToolCall(BaseModel):
    id: str
    function: ToolCallFunction


class VapiMessage(BaseModel):
    type: str
    toolCalls: list[ToolCall] = []


class VapiWebhookPayload(BaseModel):
    message: VapiMessage


class ToolCallResult(BaseModel):
    toolCallId: str
    result: str


class VapiWebhookResponse(BaseModel):
    results: list[ToolCallResult]
