import json
from fastapi import Request
from src.api.adapters.base import WebhookAdapter

class SlackAdapter(WebhookAdapter):
    """
    Slack block-kit interactive components adapter.
    """
    async def verify_signature(self, request: Request) -> bool:
        # Signature verification is performed by SlackSignatureMiddleware in the src.middleware layer.
        return True

    async def extract_payload(self, request: Request) -> dict:
        form_data = await request.form()
        payload_str = form_data.get("payload")
        if not payload_str:
            return {}
            
        payload = json.loads(payload_str)
        actions = payload.get("actions", [])
        if not actions:
            return {}
            
        action = actions[0]
        # Format of action value: "decision_TASK-ID"
        decision_raw, task_id = action.get("value").split("_", 1)
        
        status = "APPROVED" if action.get("action_id") == "hitl_approve" else "REJECTED"
        user_name = payload.get("user", {}).get("name", "Auditor")
        user_id = payload.get("user", {}).get("id")
        response_url = payload.get("response_url")
        
        return {
            "task_id": task_id,
            "status": status,
            "user_name": user_name,
            "user_id": user_id,
            "response_url": response_url
        }

    async def send_response_update(self, response_url: str, text: str) -> bool:
        """
        Asynchronously sends Slack callback updates using HTTPX.
        """
        if not response_url:
            return False
            
        import httpx
        payload = {
            "replace_original": "true",
            "text": text
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    response_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=5.0
                )
                return response.status_code == 200
        except Exception as e:
            print(f"ERROR: Failed to send Slack callback response update: {e}")
            return False
