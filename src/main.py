from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from src.api.middleware import SlackSignatureMiddleware
from src.api.routes import router
from src.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="CogniHelm Gateway API",
    description="Immutable human-in-the-loop middleware for autonomous AI agents.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to capture unhandled errors, log them,
    and return a sanitized generic JSON response.
    """
    logging.error(f"System Error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal system error occurred. Action frozen."}
    )

# Inject the security middleware for Slack callbacks
app.add_middleware(SlackSignatureMiddleware)
print("🔒 [CogniHelm]: Slack Webhook HMAC Verification & Circuit Breaker Active.")

# Include routes APIRouter
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 [CogniHelm]: Booting gateway on port {settings.port} (Environment: {settings.environment})")
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
