import os
import uuid
import time
import json
import base64
import hashlib
import jwt
from typing import Dict, Any, Optional
import hmac
import hashlib
from fastapi import Request, Response, HTTPException, Header, Depends
from starlette.middleware.base import BaseHTTPMiddleware

# --- Security: Slack Signature Verification ---
class SlackVerificationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/v1/webhooks/slack-callback":
            # Get Slack headers
            timestamp = request.headers.get("X-Slack-Request-Timestamp")
            signature = request.headers.get("X-Slack-Signature")
            signing_secret = os.getenv("SLACK_SIGNING_SECRET")

            if not signing_secret:
                print("WARNING: SLACK_SIGNING_SECRET not set. Skipping verification (DEV MODE).")
                return await call_next(request)

            # Prevent replay attacks
            if abs(time.time() - int(timestamp)) > 60 * 5:
                raise HTTPException(status_code=403, detail="Timestamp expired")

            body = await request.body()
            sig_basestring = f"v0:{timestamp}:{body.decode()}"
            my_signature = "v0=" + hmac.new(
                signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(my_signature, signature):
                raise HTTPException(status_code=403, detail="Invalid Slack signature")

        return await call_next(request)

app.add_middleware(SlackVerificationMiddleware)

# --- A2A Compliant Error Objects ---
def a2a_error(rpc_id: str, code: int, message: str):
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {
            "code": code,
            "message": message
        }
    }

# Update RS256 Logic (Mock for now, but structure is ready)
def generate_resumption_jwt(task_id: str, context_hash: str):
    # In production, load the Private Key from RSA_PRIVATE_KEY_PATH
    payload = {
        "iss": "hitl-circuit.dev",
        "sub": task_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "decision": "APPROVED",
        "approved_hash": context_hash
    }
    # Structure ready for RS256 swap once keys are provided
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
import boto3
from botocore.exceptions import ClientError

app = FastAPI(title="Universal HITL Approval API (V1 x402 V2)")

# --- Config ---
REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "HITL_Tickets")
SECRET_KEY = os.getenv("JWT_PRIVATE_KEY", "prototype-key")
CROSSMINT_COLLECTION_ID = os.getenv("CROSSMINT_ID", "cm-collection-123")

# --- AWS DynamoDB Initialization ---
# Note: In Lambda, credentials are automatically picked up from the execution role
dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

# --- x402 V2 Payment Logic ---
FIXED_FEE = "0.01" # 0.01 USDC

def get_payment_required_header():
    """Generates the base64-encoded x402 V2 challenge."""
    payload = {
        "amount": FIXED_FEE,
        "asset": "USDC",
        "chain": "base-sepolia",
        "mediator": "Crossmint",
        "payment_target": CROSSMINT_COLLECTION_ID
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()

def mock_crossmint_verify(signature: str) -> bool:
    """
    Simulates checking the Crossmint WaaS API to verify the 
    non-custodial session key signature for the routing fee.
    """
    return signature.startswith("verified-")

# --- A2A JSON-RPC Logic ---
class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: Dict[str, Any]

from ledger import CogniHelmLedger

# --- CogniHelm Immutable Ledger Initialization ---
ledger = CogniHelmLedger(table_name=TABLE_NAME, region=REGION)

@app.post("/v1/rpc")
async def a2a_rpc_handler(
    request_data: JSONRPCRequest,
    payment_signature: Optional[str] = Header(None, alias="PAYMENT-SIGNATURE")
):
    # 1. x402 V2 Payment Enforcement
    if not payment_signature or not mock_crossmint_verify(payment_signature):
        return Response(
            status_code=402,
            headers={"PAYMENT-REQUIRED": get_payment_required_header()},
            content="Payment Required"
        )

    # 2. A2A Method Routing
    if request_data.method == "tasks/send":
        return await handle_create_task(request_data)
    elif request_data.method == "tasks/get":
        return await handle_get_task(request_data)
    else:
        return a2a_error(request_data.id, -32601, "Method Not Supported")

async def handle_create_task(rpc: JSONRPCRequest):
    task_id = str(uuid.uuid4())
    agent_context = rpc.params.get("message", {}).get("parts", [{}])[0].get("text", "")
    
    # Immutable Event: AGENT_TASK_INGESTION
    try:
        ledger.append_event(
            task_id=task_id,
            event_type="AGENT_TASK_INGESTION",
            actor_id="A2A_AGENT_CLIENT",
            payload={"context": agent_context},
            reasoning="Initial ingestion of autonomous agent execution request."
        )
        print(f"CogniHelm Ledger: Task {task_id} Ingested.")
    except Exception:
        return a2a_error(rpc.id, -32000, "Ledger Append Failure")

    return {
        "jsonrpc": "2.0",
        "id": rpc.id,
        "result": {
            "task_id": task_id,
            "status": "working", # A2A working = Human notified
        }
    }

async def handle_get_task(rpc: JSONRPCRequest):
    task_id = rpc.params.get("task_id")
    
    # Query the audit trail to find the LATEST state
    try:
        events = ledger.get_audit_trail(task_id)
    except Exception:
        return a2a_error(rpc.id, -32000, "Ledger Query Failure")

    if not events:
        return a2a_error(rpc.id, -32602, "Task Not Found")

    # The latest event (last in the list due to SK=timestamp) defines current status
    latest_event = events[-1]
    
    # Map Event Types to A2A Statuses
    status_map = {
        "AGENT_TASK_INGESTION": "working",
        "HUMAN_APPROVAL_DECISION": "completed",
        "HUMAN_DENIAL_DECISION": "failed"
    }
    
    current_status = status_map.get(latest_event['event_type'], "failed")
    
    result = {
        "task_id": task_id,
        "status": current_status
    }

    # Direct Injection Strategy: Return JWT if completed
    if current_status == 'completed':
        resumption_jwt = generate_resumption_jwt(task_id, latest_event['payload_hash'])
        result["result"] = resumption_jwt

    return {
        "jsonrpc": "2.0",
        "id": rpc.id,
        "result": result
    }

# --- Human Interaction (Slack Callback) ---
@app.post("/v1/webhooks/slack-callback")
async def slack_callback(payload: Dict[str, Any]):
    task_id = payload.get("task_id")
    action = payload.get("action") # "APPROVE" or "DENY"

    event_type = "HUMAN_APPROVAL_DECISION" if action == "APPROVE" else "HUMAN_DENIAL_DECISION"
    actor_id = payload.get("user_id", "SLACK_OPERATOR")

    # Immutable Event: APPEND THE DECISION (No UpdateItem)
    try:
        ledger.append_event(
            task_id=task_id,
            event_type=event_type,
            actor_id=actor_id,
            payload={"action": action},
            reasoning=f"Human operator decision received via Slack for task {task_id}."
        )
        print(f"CogniHelm Ledger: Human decision recorded for {task_id}.")
    except Exception:
        raise HTTPException(status_code=500, detail="Ledger Write Failure")

    return {"status": "success", "recorded_event": event_type}
