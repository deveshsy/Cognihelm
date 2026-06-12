from fastapi import Request
from src.adapters.base import WebhookAdapter
from src.config import get_settings

class TelegramAdapter(WebhookAdapter):
    """
    Telegram Inline Keyboard Webhook Adapter.
    Validates requests using X-Telegram-Bot-Api-Secret-Token header.
    """
    async def verify_signature(self, request: Request) -> bool:
        settings = get_settings()
        secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not secret_header:
            print("SECURITY WARNING: Missing X-Telegram-Bot-Api-Secret-Token header in Telegram callback.")
            return False
        return secret_header == settings.telegram_bot_token

    async def extract_payload(self, request: Request) -> dict:
        try:
            payload = await request.json()
        except Exception as e:
            print(f"ERROR: Failed to parse Telegram JSON payload: {e}")
            return {}

        callback_query = payload.get("callback_query", {})
        if not callback_query:
            return {}

        # Expected data format: "approve_TASK-ID" or "reject_TASK-ID"
        data = callback_query.get("data")
        if not data:
            return {}

        try:
            decision, task_id = data.split("_", 1)
        except ValueError:
            return {}

        status = "APPROVED" if decision.lower() in ["approve", "approved", "hitl_approve"] else "REJECTED"

        # Sender information (handling python reserved from keyword via dict get)
        from_user = callback_query.get("from", {})
        user_id = str(from_user.get("id", "telegram-user-id"))
        user_name = from_user.get("username") or f"Telegram User {user_id}"

        return {
            "task_id": task_id,
            "status": status,
            "user_name": user_name,
            "user_id": user_id,
            "response_url": None
        }
