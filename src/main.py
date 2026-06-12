import uuid
import json
import urllib.request
from fastapi import FastAPI, Request, HTTPException
from src.aws_ledger import append_ledger_entry, get_latest_task_status
from src.adapters.slack_adapter import SlackAdapter
from src.adapters.teams_adapter import TeamsAdapter
from src.adapters.whatsapp_adapter import WhatsappAdapter
from src.adapters.telegram_adapter import TelegramAdapter
from src.adapters.discord_adapter import DiscordAdapter
from src.config import get_settings

settings = get_settings()

adapters = {
    "slack": SlackAdapter(),
    "teams": TeamsAdapter(),
    "whatsapp": WhatsappAdapter(),
    "telegram": TelegramAdapter(),
    "discord": DiscordAdapter()
}

app = FastAPI(title="CogniHelm HITL Gateway")

# DYNAMIC SECURITY CHECK: Look for private enterprise extensions
try:
    from ee.advanced_auth import SlackSignatureMiddleware
    from ee.circuit_breaker import is_task_resolved
    
    # Inject the proprietary security middleware if available
    app.add_middleware(SlackSignatureMiddleware)
    HAS_ENTERPRISE_SECURITY = True
    print("🔒 [CogniHelm]: Enterprise Security & Circuit Breaker Active.")
except ImportError:
    HAS_ENTERPRISE_SECURITY = False
    is_task_resolved = lambda task_id: False  # Fallback for Open-Core
    print("🟢 [CogniHelm]: Running Open-Core mode (Development/Unverified).")

@app.get("/")
async def health():
    return {"status": "online", "gateway": "CogniHelm v1.0"}

@app.get("/v1/webhooks/{platform}-callback")
async def handle_webhook_verification(platform: str, request: Request):
    """Handles incoming subscription verification challenges (e.g. GET from WhatsApp)."""
    adapter = adapters.get(platform.lower())
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Platform adapter '{platform}' not found")
        
    if platform.lower() == "whatsapp":
        # Check challenge parameters
        params = request.query_params
        if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == settings.whatsapp_verify_token:
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(content=params.get("hub.challenge", ""))
            
    return {"status": "ignored"}

@app.post("/v1/webhooks/{platform}-callback")
async def handle_webhook_callback(platform: str, request: Request):
    """Handles incoming human decisions from Slack or MS Teams with a Circuit Breaker."""
    adapter = adapters.get(platform.lower())
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Platform adapter '{platform}' not found")

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
        if platform.lower() == "slack" and response_url:
            update_message = {
                "replace_original": "true",
                "text": f"🔒 *LOCKED:* Task `{task_id}` has already been resolved."
            }
            req = urllib.request.Request(
                response_url,
                data=json.dumps(update_message).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req)
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
    if platform.lower() == "slack" and response_url:
        emoji = "✅" if status == "APPROVED" else "❌"
        update_message = {
            "replace_original": "true",
            "text": f"{emoji} *Action {status}* by @{user_name}\nTask ID: `{task_id}`"
        }
        req = urllib.request.Request(
            response_url,
            data=json.dumps(update_message).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req)

    return {"status": "processed", "task_id": task_id, "decision": status}

@app.get("/v1/task/{task_id}/status")
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

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 [CogniHelm]: Booting gateway on port {settings.port} (Environment: {settings.environment})")
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
