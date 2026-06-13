import uuid
import json
import urllib.request
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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

app = FastAPI(
    title="CogniHelm Gateway API",
    description="Immutable human-in-the-loop middleware for autonomous AI agents.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"System Error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal system error occurred. Action frozen."}
    )

from src.middleware import SlackSignatureMiddleware
from src.circuit_breaker import is_task_resolved

# Inject the security middleware for Slack callbacks
app.add_middleware(SlackSignatureMiddleware)
print("🔒 [CogniHelm]: Slack Webhook HMAC Verification & Circuit Breaker Active.")

@app.get("/")
async def health():
    return {"status": "online", "gateway": "CogniHelm v1.0"}

@app.get("/v1/webhooks/{platform}-callback")
async def handle_webhook_verification(platform: str, request: Request):
    """Handles incoming subscription verification challenges (e.g. GET from WhatsApp)."""
    adapter = adapters.get(platform.lower())
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Platform adapter '{platform}' not found")
        
    response = await adapter.handle_verification(request)
    if response:
        return response
            
    return {"status": "ignored"}

@app.post("/v1/webhooks/{platform}-callback")
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
