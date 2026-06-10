import os
import urllib.request
import json
from dotenv import load_dotenv
from src.aws_ledger import append_ledger_entry, get_latest_task_status, is_task_resolved

# Load credentials from your .env file
load_dotenv()

def dispatch_approval_card(task_id: str, agent_name: str, action: str, details: dict):
    """
    Sends an interactive Block Kit UI card to Slack ONLY if the task is unresolved.
    """
    # --- 1. PRE-FLIGHT CHECK (Ledger Awareness) ---
    if is_task_resolved(task_id):
        print(f"ABORT: Task {task_id} is already resolved in the ledger. No card sent.")
        return {"ok": False, "error": "task_already_resolved"}

    latest = get_latest_task_status(task_id)
    if latest and latest.get("status") == "PENDING":
        print(f"SKIP: Task {task_id} is already PENDING human approval. Avoiding duplicate notification.")
        return {"ok": False, "error": "task_already_pending"}

    # --- 2. DISPATCH TO SLACK ---
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    channel = "#ai-apporvals" 
    details_str = "\n".join([f"*{k}:* {v}" for k, v in details.items()])

    payload = {
        "channel": channel,
        "text": f"High-Risk Action Requested by {agent_name}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚠️ Agent Authorization Required",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Agent:* {agent_name}\n*Task ID:* `{task_id}`\n*Proposed Action:* `{action}`\n\n*Context & Payload:*\n{details_str}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Approve Action",
                            "emoji": True
                        },
                        "style": "primary",
                        "value": f"approve_{task_id}",
                        "action_id": "hitl_approve"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Reject",
                            "emoji": True
                        },
                        "style": "danger",
                        "value": f"reject_{task_id}",
                        "action_id": "hitl_reject"
                    }
                ]
            }
        ]
    }

    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bot_token}"
        }
    )
    
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode("utf-8"))
        
        if result.get("ok"):
            # --- 3. LOG INITIAL PENDING STATE ---
            # Now the ledger knows a request has been dispatched.
            append_ledger_entry(
                task_id=task_id,
                status="PENDING",
                metadata={
                    "agent": agent_name,
                    "action": action,
                    "details": details,
                    "slack_ts": result.get("ts")
                }
            )
            print(f"SUCCESS: Card sent and PENDING state recorded for {task_id}")
        else:
            print(f"Failed to post to Slack: {result}")
        return result
    except Exception as e:
        print(f"Error communicating with Slack: {e}")
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    # Test sending a card
    print("Dispatching test card to Slack...")
    dispatch_approval_card(
        task_id="FIN_TXN#TEST99",
        agent_name="LangGraph_Finance_Bot",
        action="execute_wire_transfer",
        details={"amount": "$50,000", "destination": "Offshore Acct 99182"}
    )
    print("Check your #ai-approvals channel!")
