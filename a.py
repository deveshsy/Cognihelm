import json
import base64
import requests
import time
from typing import Dict, Any

API_URL = "http://localhost:8000/v1/rpc"

def call_hitl_gateway(message: str):
    payload = {
        "jsonrpc": "2.0",
        "id": "req-1",
        "method": "tasks/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"text": message}]
            }
        }
    }

    print("Attempting to send HITL Task...")
    response = requests.post(API_URL, json=payload)

    # Handle x402 V2 Challenge
    if response.status_code == 402:
        payment_required = response.headers.get("PAYMENT-REQUIRED")
        challenge = json.loads(base64.b64decode(payment_required).decode())
        print(f"x402 V2 Challenge Received: {challenge['amount']} {challenge['asset']} via {challenge['mediator']}")
        
        # In production, the agent calls Crossmint to sign the UserOperation
        # Simulating a verified signature here
        mock_signature = f"verified-sig-{int(time.time())}"
        print("Retrying with PAYMENT-SIGNATURE...")
        
        response = requests.post(
            API_URL, 
            json=payload, 
            headers={"PAYMENT-SIGNATURE": mock_signature}
        )

    if response.status_code == 202 or response.status_code == 200:
        task_info = response.json()["result"]
        task_id = task_info["task_id"]
        print(f"Task Created Successfully: {task_id}. Status: {task_info['status']}")
        return task_id
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def poll_task_status(task_id: str):
    payload = {
        "jsonrpc": "2.0",
        "id": "poll-1",
        "method": "tasks/get",
        "params": {"task_id": task_id}
    }

    while True:
        print(f"Polling status for {task_id}...")
        # Note: We must include the signature in every poll for x402 V2 if enforced per-request
        response = requests.post(
            API_URL, 
            json=payload, 
            headers={"PAYMENT-SIGNATURE": "verified-polling"}
        )
        
        result = response.json()["result"]
        if result["status"] == "completed":
            print("\nTASK COMPLETED!")
            print(f"Resumption JWT: {result['result']}")
            break
        elif result["status"] == "failed":
            print("\nTASK FAILED (DENIED).")
            break
        
        time.sleep(5)

if __name__ == "__main__":
    tid = call_hitl_gateway("Approve refund of $50.00 for user tx-123")
    if tid:
        poll_task_status(tid)
