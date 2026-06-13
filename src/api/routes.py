from fastapi import APIRouter, Request, HTTPException
from src.db.aws_ledger import append_ledger_entry, get_latest_task_status
from src.services.circuit_breaker import is_task_resolved
from src.core.config import get_settings
from src.api.adapters.slack_adapter import SlackAdapter
from src.api.adapters.teams_adapter import TeamsAdapter
from src.api.adapters.whatsapp_adapter import WhatsappAdapter
from src.api.adapters.telegram_adapter import TelegramAdapter
from src.api.adapters.discord_adapter import DiscordAdapter

settings = get_settings()
router = APIRouter()

adapters = {
    "slack": SlackAdapter(),
    "teams": TeamsAdapter(),
    "whatsapp": WhatsappAdapter(),
    "telegram": TelegramAdapter(),
    "discord": DiscordAdapter()
}

@router.get("/health")
async def health():
    """Simple API health check endpoint."""
    return {"status": "online", "gateway": "CogniHelm v1.0"}

@router.get("/v1/webhooks/{platform}-callback")
async def handle_webhook_verification(platform: str, request: Request):
    """Handles incoming subscription verification challenges (e.g. GET from WhatsApp)."""
    adapter = adapters.get(platform.lower())
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Platform adapter '{platform}' not found")
        
    response = await adapter.handle_verification(request)
    if response:
        return response
            
    return {"status": "ignored"}

@router.post("/v1/webhooks/{platform}-callback")
async def handle_webhook_callback(platform: str, request: Request):
    """Handles incoming human decisions from Slack or MS Teams with signature verification and a Circuit Breaker."""
    adapter = adapters.get(platform.lower())
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Platform adapter '{platform}' not found")

    # Enforce platform-specific cryptographic signature verification
    if not await adapter.verify_signature(request):
        raise HTTPException(status_code=401, detail="Unauthorized: Signature verification failed")

    # Extract standard payload properties via the selected adapter
    extracted = await adapter.extract_payload(request)
    task_id = extracted.get("task_id")
    status = extracted.get("status")
    user_name = extracted.get("user_name", "Auditor")
    user_id = extracted.get("user_id")
    response_url = extracted.get("response_url")

    if not task_id or not status:
        return {"status": "ignored"}

    # --- LINEARITY CHECK (Circuit Breaker) ---
    if is_task_resolved(task_id):
        if response_url:
            await adapter.send_response_update(
                response_url,
                f"🔒 *LOCKED:* Task `{task_id}` has already been resolved."
            )
        return {"status": "locked", "task_id": task_id}

    # Retrieve the payload_hash from the initial PENDING entry
    pending_record = get_latest_task_status(task_id)
    payload_hash = pending_record.get("payload_hash") if pending_record else None

    # Append the decision to the ledger
    append_ledger_entry(
        task_id=task_id,
        status=status,
        metadata={
            "platform": platform,
            "auditor": user_name,
            "auditor_id": user_id
        },
        payload_hash=payload_hash
    )

    # Perform platform-specific response actions
    if response_url:
        emoji = "✅" if status == "APPROVED" else "❌"
        await adapter.send_response_update(
            response_url,
            f"{emoji} *Action {status}* by @{user_name}\nTask ID: `{task_id}`"
        )

    return {"status": "processed", "task_id": task_id, "decision": status}

@router.get("/v1/task/{task_id}/status")
async def check_task_status(task_id: str):
    """Polling endpoint for agents to check authorization status."""
    record = get_latest_task_status(task_id)
    if not record:
        return {"status": "NOT_FOUND"}
        
    response_data = {
        "task_id": task_id,
        "status": record.get("status"),
        "timestamp": record.get("timestamp"),
        "metadata": record.get("metadata"),
        "payload_hash": record.get("payload_hash")
    }
    if record.get("status") == "APPROVED":
        response_data["authorized_at"] = record.get("timestamp")
    elif record.get("status") == "REJECTED":
        response_data["denied_at"] = record.get("timestamp")
    return response_data
