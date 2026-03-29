"""
main.py — FastAPI entry point for the EPOWERdoc automation bridge.

Workflow:
  1. Web dashboard POSTs patient data to /webhook/register over a secure tunnel.
  2. FastAPI validates the shared secret and the payload schema.
  3. The pywinauto hook (app.epower_hook) drives the EPOWERdoc GUI synchronously
     in a thread executor so the async event loop is never blocked.
  4. HTTP 200 {"status": "success"} or HTTP 400 {"detail": "<metadata>"} is
     returned through the tunnel back to the dashboard.

HIPAA constraints enforced here:
  - No PHI field values appear in any log statement.
  - Webhook secret is compared with hmac.compare_digest (constant-time).
  - StreamHandler only — no FileHandler, so nothing lands on disk.
"""

import asyncio
import hmac
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request, status

from app.config import settings
from app.epower_hook import register_patient
from app.models import PatientPayload


# ── Logging (metadata only — no PHI) ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    # FileHandler intentionally excluded: log files could persist PHI.
)
logger = logging.getLogger(__name__)


# ── Application lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("EPOWERdoc automation server starting up.")
    yield
    logger.info("EPOWERdoc automation server shutting down.")


app = FastAPI(
    title="EPOWERdoc Automation Bridge",
    version="0.1.0",
    docs_url=None,   # disable Swagger UI in production
    redoc_url=None,
    lifespan=lifespan,
)


# ── Security helper ───────────────────────────────────────────────────────────

def _verify_webhook_secret(provided: str) -> None:
    """
    Constant-time comparison against the configured webhook secret.
    Raises HTTP 401 on mismatch to prevent timing-based secret enumeration.
    """
    expected = settings.webhook_secret.encode()
    if not hmac.compare_digest(expected, provided.encode()):
        logger.warning("Webhook request rejected — invalid secret.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret.",
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Liveness probe — returns 200 when the server is running."""
    return {"status": "ok"}


@app.post("/webhook/register", status_code=status.HTTP_200_OK)
async def webhook_register(
    payload: PatientPayload,
    x_webhook_secret: str = Header(..., alias="X-Webhook-Secret"),
):
    """
    Receive a patient registration payload and drive EPOWERdoc via pywinauto.

    Expected headers:
      X-Webhook-Secret: <shared secret matching WEBHOOK_SECRET in .env>

    Expected body (JSON):
      {
        "first_name":       "...",
        "last_name":        "...",
        "dob":              "YYYY-MM-DD",
        "chief_complaint":  "...",
        "insurance_id":     "..."
      }

    Returns:
      200  {"status": "success"}         — EPOWERdoc confirmed the save
      400  {"detail": "<metadata msg>"}  — automation or EHR error
      401  {"detail": "..."}             — bad webhook secret
      422  {"detail": [...]}             — Pydantic validation failure
    """
    _verify_webhook_secret(x_webhook_secret)

    logger.info("Webhook received — dispatching registration workflow.")

    try:
        # pywinauto is synchronous; run it in a thread to avoid blocking
        # the async event loop.
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, register_patient, payload)
    except RuntimeError as exc:
        # exc.args[0] contains only metadata — no PHI (enforced in epower_hook)
        logger.error("Registration workflow failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Unexpected error during registration workflow.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected automation error occurred.",
        )
    finally:
        # Explicitly delete the payload reference so the GC can reclaim PHI
        # from RAM as soon as possible.
        del payload

    logger.info("Registration workflow returned: %s", result.get("status"))
    return result


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,       # never enable reload in production
        access_log=False,   # access logs could echo request bodies containing PHI
    )
