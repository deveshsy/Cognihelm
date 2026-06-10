import hmac
import hashlib
import os
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

load_dotenv()

class SlackSignatureMiddleware(BaseHTTPMiddleware):
    """
    Cryptographic verification middleware for Slack Webhooks.
    Ensures that requests originate from Slack and haven't been tampered with.
    """
    async def dispatch(self, request: Request, call_next):
        # Verification for the specific slack callback route
        if request.url.path == "/v1/webhooks/slack-callback":
            timestamp = request.headers.get("X-Slack-Request-Timestamp")
            signature = request.headers.get("X-Slack-Signature")
            signing_secret = os.getenv("SLACK_SIGNING_SECRET")

            if not signing_secret:
                print("CRITICAL: SLACK_SIGNING_SECRET not found.")
                raise HTTPException(status_code=500, detail="Security configuration missing")

            # 1. Prevent Replay Attacks (5 minute window)
            if not timestamp or abs(time.time() - int(timestamp)) > 60 * 5:
                raise HTTPException(status_code=403, detail="Timestamp verification failed")

            # 2. Construct the signature basestring
            body = await request.body()
            sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
            
            # 3. Compute HMAC SHA256
            computed_signature = "v0=" + hmac.new(
                signing_secret.encode('utf-8'),
                sig_basestring.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            # 4. Secure compare
            if not hmac.compare_digest(computed_signature, signature or ""):
                print("SECURITY ALERT: Invalid Slack signature.")
                raise HTTPException(status_code=403, detail="Invalid signature")

        return await call_next(request)
