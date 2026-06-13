import hmac
import hashlib
from fastapi import Request
from src.api.adapters.base import WebhookAdapter
from src.core.config import get_settings

class WhatsappAdapter(WebhookAdapter):
    """
    Meta WhatsApp Cloud API Webhook Adapter.
    Supports verify token verification challenge (GET) and SHA-256 HMAC payload signatures (POST).
    """
    async def handle_verification(self, request: Request):
        """Handles the initial Meta verification challenge (GET)."""
        settings = get_settings()
        params = request.query_params
        if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == settings.whatsapp_verify_token:
            from fastapi.responses import PlainTextResponse
            challenge = params.get("hub.challenge", "")
            return PlainTextResponse(content=challenge)
        return None

    async def verify_signature(self, request: Request) -> bool:
        settings = get_settings()

        # 1. Verification Challenge (GET)
        if request.method == "GET":
            return await self.handle_verification(request) is not None

        # 2. Payload Signature Check (POST)
        signature_header = request.headers.get("X-Hub-Signature-256")
        if not signature_header or not signature_header.startswith("sha256="):
            print("SECURITY WARNING: Missing or malformed X-Hub-Signature-256 header in WhatsApp callback.")
            return False

        expected_sig = signature_header.split("sha256=", 1)[1]
        body = await request.body()

        # In production, Meta signs payloads using the Meta App Secret.
        # We reuse the whatsapp_verify_token config as a placeholder key here.
        key = settings.whatsapp_verify_token or "whatsapp-app-secret"
        computed_sig = hmac.new(
            key.encode("utf-8"),
            body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed_sig, expected_sig)

    async def extract_payload(self, request: Request) -> dict:
        """
        Extracts task_id and decision action from WhatsApp entry changes.
        """
        try:
            payload = await request.json()
        except Exception as e:
            print(f"ERROR: Failed to parse WhatsApp JSON payload: {e}")
            return {}

        try:
            entry = payload.get("entry", [])[0]
            change = entry.get("changes", [])[0]
            value = change.get("value", {})
            message = value.get("messages", [])[0]
            interactive = message.get("interactive", {})
            button_reply = interactive.get("button_reply", {})

            # Expected ID format: "approve_TASK-ID" or "reject_TASK-ID"
            button_id = button_reply.get("id")
            phone_number = message.get("from")  # Sender's WhatsApp ID/phone number

            if not button_id or not phone_number:
                return {}

            decision, task_id = button_id.split("_", 1)
            status = "APPROVED" if decision.lower() in ["approve", "approved", "hitl_approve"] else "REJECTED"

            return {
                "task_id": task_id,
                "status": status,
                "user_name": f"WhatsApp: {phone_number}",
                "user_id": phone_number,
                "response_url": None
            }
        except (IndexError, KeyError, ValueError) as e:
            print(f"ERROR: WhatsApp payload parsing structure mismatch: {e}")
            return {}
