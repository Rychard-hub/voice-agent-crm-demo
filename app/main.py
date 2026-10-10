import hmac
import logging

from fastapi import FastAPI, Header, HTTPException, Request

from .config import settings
from .schemas import VapiWebhookPayload, VapiWebhookResponse
from .vapi_webhook import handle_tool_call

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Voice Agent CRM Demo")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook/vapi", response_model=VapiWebhookResponse)
async def vapi_webhook(request: Request, x_vapi_secret: str | None = Header(default=None)):
    # Vapi sends the `server.secret` you configured back as the x-vapi-secret
    # header on every request (not an HMAC signature) -- compare it as a
    # shared secret, timing-safe since it's a direct string comparison.
    if settings.vapi_webhook_secret and not hmac.compare_digest(
        x_vapi_secret or "", settings.vapi_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="invalid webhook secret")

    body = await request.json()
    payload = VapiWebhookPayload.model_validate(body)

    if payload.message.type != "tool-calls":
        return VapiWebhookResponse(results=[])

    results = [await handle_tool_call(tc) for tc in payload.message.toolCalls]
    return VapiWebhookResponse(results=results)
