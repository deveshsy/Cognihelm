import uuid
import json
import urllib.request
from fastapi import FastAPI, Request
from src.slack_auth import SlackSignatureMiddleware
from src.aws_ledger import append_ledger_entry, get_latest_task_status, is_task_resolved

app = FastAPI(title="CogniHelm HITL Gateway")

# Apply security middleware
app.add_middleware(SlackSignatureMiddleware)

@app.get("/")
async def health():
    return {"status": "online", "gateway": "CogniHelm v1.0"}

@app.post("/v1/webhooks/slack-callback")
async def handle_slack_event(request: Request):
    """Handles interactive Slack button clicks with a Circuit Breaker."""
    form_data = await request.form()
    payload = json.loads(form_data.get("payload"))
    
    actions = payload.get("actions", [])
    if not actions:
        return {"status": "ignored"}

    action = actions[0]
    # Format: "decision_TASK-ID"
    decision_raw, task_id = action.get("value").split("_", 1)
    response_url = payload.get("response_url")
    user_name = payload.get("user", {}).get("name", "Auditor")

    # --- LINEARITY CHECK (Circuit Breaker) ---
    if is_task_resolved(task_id):
        update_message = {
            "replace_original": "true",
            "text": f"🔒 *LOCKED:* Task `{task_id}` has already been resolved."
        }
    else:
        status = "APPROVED" if action.get("action_id") == "hitl_approve" else "REJECTED"
        emoji = "✅" if status == "APPROVED" else "❌"
        
        append_ledger_entry(
            task_id=task_id,
            status=status,
            metadata={
                "auditor": user_name,
                "slack_id": payload.get("user", {}).get("id")
            }
        )
        
        update_message = {
            "replace_original": "true",
            "text": f"{emoji} *Action {status}* by @{user_name}\nTask ID: `{task_id}`"
        }

    # Update Slack UI
    req = urllib.request.Request(
        response_url,
        data=json.dumps(update_message).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req)
    return {"status": "processed"}

@app.get("/v1/task/{task_id}/status")
async def check_task_status(task_id: str):
    """Polling endpoint for agents to check authorization status."""
    record = get_latest_task_status(task_id)
    if not record:
        return {"status": "NOT_FOUND"}
        
    return {
        "task_id": task_id,
        "status": record.get("status"),
        "timestamp": record.get("timestamp"),
        "metadata": record.get("metadata")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
