from fastapi import Request
from src.adapters.base import WebhookAdapter
from src.config import get_settings

class DiscordAdapter(WebhookAdapter):
    """
    Discord Message Component Webhook Adapter.
    Uses Ed25519 signatures. Implements extraction for interactive buttons.
    """
    async def verify_signature(self, request: Request) -> bool:
        """
        Stub: Discord Ed25519 signature validation.
        
        NOTE: In a production environment, Discord requires validating incoming requests
        using the nacl.signing.VerifyKey (part of PyNaCl) against the X-Signature-Ed25519
        and X-Signature-Timestamp headers, using settings.discord_public_key.
        """
        signature = request.headers.get("X-Signature-Ed25519")
        timestamp = request.headers.get("X-Signature-Timestamp")
        
        if not signature or not timestamp:
            print("SECURITY WARNING: Missing Discord signature or timestamp headers.")
            return False
            
        # Placeholder validation check (requires PyNaCl for actual implementation)
        return True

    async def extract_payload(self, request: Request) -> dict:
        try:
            payload = await request.json()
        except Exception as e:
            print(f"ERROR: Failed to parse Discord JSON payload: {e}")
            return {}

        # Discord interactions check (type 3 corresponds to Message Components like buttons)
        if payload.get("type") != 3:
            return {}

        data_obj = payload.get("data", {})
        custom_id = data_obj.get("custom_id")  # Expected format: "approve_TASK-ID" or "reject_TASK-ID"
        if not custom_id:
            return {}

        try:
            decision, task_id = custom_id.split("_", 1)
        except ValueError:
            return {}

        status = "APPROVED" if decision.lower() in ["approve", "approved", "hitl_approve"] else "REJECTED"

        # Determine user details (inside guild member block, or fallback to direct user block)
        member = payload.get("member", {})
        user = member.get("user", {}) or payload.get("user", {})
        user_name = user.get("username", "Discord Auditor")
        user_id = user.get("id", "discord-user-id")

        return {
            "task_id": task_id,
            "status": status,
            "user_name": user_name,
            "user_id": user_id,
            "response_url": None
        }
