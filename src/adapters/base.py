from abc import ABC, abstractmethod
from fastapi import Request

class WebhookAdapter(ABC):
    """
    Abstract Base Class for Chat Platform Webhook Adapters.
    Decouples platform-specific payloads and signature checks from core gateway logic.
    """
    @abstractmethod
    async def verify_signature(self, request: Request) -> bool:
        """
        Verifies the incoming cryptographic signature from the platform.
        Returns True if valid, False otherwise.
        """
        pass

    @abstractmethod
    async def extract_payload(self, request: Request) -> dict:
        """
        Extracts task_id and status from the platform's request payload.
        Returns a dictionary containing:
        {
            "task_id": str,
            "status": str,       # "APPROVED" or "REJECTED"
            "user_name": str,
            "user_id": str,
            "response_url": str  # optional response hook URL (e.g. for Slack response_url)
        }
        """
        pass
