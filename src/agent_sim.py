import time
import requests
import sys
import subprocess
import json
import hashlib

# Gateway URL (Your FastAPI server location)
GATEWAY_URL = "http://localhost:8000"
TASK_ID = f"FIN_TXN#PROD_{int(time.time())}"

# High-value action payload definition
PAYLOAD = {
    "amount": 45000,
    "currency": "USD",
    "destination": "Account_A"
}

def main():
    print("🤖 [Agent]: Initializing High-Value Asset Allocation...")
    print(f"🤖 [Agent]: Core Action requires human authorization. Target Task ID: `{TASK_ID}`")
    
    # Calculate SHA-256 hash of the payload deterministically
    payload_str = json.dumps(PAYLOAD, sort_keys=True)
    payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()
    print(f"🤖 [Agent]: Calculated local payload SHA-256: {payload_hash}")
    
    # Step 1: Trigger the Slack card UI script to notify the human
    print("🤖 [Agent]: Dispatching authorization request to CogniHelm Gateway...")
    try:
        # Executes your existing slack_ui.py script, passing TASK_ID and payload_hash
        import os
        env = os.environ.copy()
        env["PYTHONPATH"] = "."
        subprocess.run([sys.executable, "src/slack_ui.py", TASK_ID, payload_hash], check=True, env=env)
    except Exception as e:
        print(f"❌ [Error]: Failed to dispatch Slack card notification: {e}")
        sys.exit(1)
        
    print("🟢 [Agent]: Slack Card successfully dispatched to #ai-approvals.")
    print("⏳ [Agent]: Entering Hold State. Polling CogniHelm immutable ledger for signature...")
    
    # Step 2: The Polling Loop (Checking for human sign-off)
    import urllib.parse
    encoded_task_id = urllib.parse.quote(TASK_ID)
    status_url = f"{GATEWAY_URL}/v1/task/{encoded_task_id}/status"
    
    while True:
        try:
            response = requests.get(status_url)
            if response.status_code == 200:
                data = response.json()
                current_status = data.get("status")
                
                if current_status == "PENDING":
                    print("🔒 [Agent State]: PAUSED - Awaiting compliance officer action in Slack... (Retrying in 5s)")
                elif current_status == "APPROVED":
                    print("\n⚡ [Agent State]: RESUMED! Cryptographic human signature verified in ledger.")
                    print(f"✅ [Success]: Authorized timestamp: {data.get('authorized_at')}")
                    
                    # Core Interlock Check
                    db_payload_hash = data.get("payload_hash")
                    recalculated_hash = hashlib.sha256(json.dumps(PAYLOAD, sort_keys=True).encode()).hexdigest()
                    
                    print(f"🔒 [Agent State]: Performing payload interlock check...")
                    print(f"🔒 [Agent State]: Recalculated Hash: {recalculated_hash}")
                    print(f"🔒 [Agent State]: Database Hash:     {db_payload_hash}")
                    
                    if recalculated_hash == db_payload_hash:
                        print("✅ [Interlock Verified]: Payload integrity guaranteed. Executing transfer.")
                        print("🚀 [Agent]: Successfully transferred $45,000 USD to production clearing house. Loop Closed.")
                    else:
                        print("🚨 [CRITICAL ALERT]: Payload hash mismatch detected! Potential tampering or Semantic Drift.")
                        print("🛑 [FATAL]: Halting execution immediately to protect funds. Core system safe.")
                        sys.exit(1)
                    break
                elif current_status == "REJECTED":
                    print("\n🛑 [Agent State]: HALTED! Action explicitly denied by compliance auditor.")
                    print(f"❌ [Failure]: Denied timestamp: {data.get('denied_at')}")
                    print("📋 [Agent]: Reverting local state changes and logging denial event. Core system safe.")
                    break
            else:
                print(f"⚠️ [Warning]: Gateway returned status code {response.status_code}. Retrying...")
                
        except requests.exceptions.ConnectionError:
            print("❌ [Error]: Cannot connect to CogniHelm Gateway. Is `src/main.py` running?")
            
        time.sleep(5)

if __name__ == "__main__":
    main()
