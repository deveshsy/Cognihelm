from abc import ABC, abstractmethod
from fastapi import Request, Response

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

    async def handle_verification(self, request: Request) -> Response | None:
        """
        Handles platform verification challenges (e.g. GET subscription checks).
        Returns a Response object or None if not supported.
        """
        return None

    async def send_response_update(self, response_url: str, text: str) -> bool:
        """
        Sends an asynchronous callback response update to the platform (if supported).
        Returns True if successful, False otherwise.
        """
        return False
