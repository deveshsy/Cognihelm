from fastapi import Request
from src.adapters.base import WebhookAdapter

class TeamsAdapter(WebhookAdapter):
    """
    Microsoft Teams Adaptive Cards Webhook Adapter.
    Processes interactive Action.Submit / Action.Execute compliance decisions.
    """
    async def verify_signature(self, request: Request) -> bool:
        """
        Extracts and verifies the JWT from the Authorization header sent by Microsoft Bot Framework.
        
        NOTE: In a production environment, you should perform full cryptographic signature 
        verification of the JWT using Microsoft's JSON Web Key Set (JWKS) endpoints.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            print("SECURITY WARNING: Missing Authorization header in Teams callback.")
            return False
            
        if not auth_header.startswith("Bearer "):
            print("SECURITY WARNING: Invalid token format in Teams callback (must start with 'Bearer ').")
            return False
            
        # Extract JWT token string
        jwt_token = auth_header.split(" ", 1)[1]
        
        # Token exists (acting as placeholder verification)
        return True

    async def extract_payload(self, request: Request) -> dict:
        """
        Extracts task_id and decision action from Teams Adaptive Card JSON payload.
        """
        try:
            payload = await request.json()
        except Exception as e:
            print(f"ERROR: Failed to parse JSON body from Teams callback: {e}")
            return {}

        # Teams submits card actions data in the 'value' object of the request body
        value = payload.get("value", {})
        task_id = value.get("task_id")
        action = value.get("action")  # Expecting "approve" or "reject"
        
        if not task_id or not action:
            return {}

        # Map to standard gateway status
        status = "APPROVED" if action.lower() in ["approve", "approved", "hitl_approve"] else "REJECTED"

        # Extract actor/auditor identity from 'from' block (handling reserved keyword)
        from_user = payload.get("from", {})
        user_name = from_user.get("name", "Teams Auditor")
        user_id = from_user.get("id", "teams-user-id")

        return {
            "task_id": task_id,
            "status": status,
            "user_name": user_name,
            "user_id": user_id,
            "response_url": None
        }
