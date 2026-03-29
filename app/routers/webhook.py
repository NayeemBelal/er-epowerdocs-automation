"""
routers/webhook.py — All inbound webhook endpoints.

Adding a new flow = add one import and one @router.post() block.
Nothing else in the codebase needs to change.
"""

import asyncio
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, status

from app.config import settings
from app.models.register_patient import RegisterPatientPayload
from app.models.print_labels import PrintLabelsPayload
from app.flows import register_patient as register_patient_flow
from app.flows import print_labels as print_labels_flow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook")


# ── Shared security ───────────────────────────────────────────────────────────

def _verify_secret(provided: str) -> None:
    """Constant-time webhook secret check. Raises 401 on mismatch."""
    if not hmac.compare_digest(
        settings.webhook_secret.encode(), provided.encode()
    ):
        logger.warning("Webhook rejected — invalid secret.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret.",
        )


# ── Shared flow dispatcher ────────────────────────────────────────────────────

async def _run_flow(flow_fn, payload):
    """
    Run a synchronous pywinauto flow in a thread executor.
    Handles RuntimeError → 400, unexpected errors → 500.
    Deletes the payload from memory when done.
    """
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, flow_fn, payload)
    except RuntimeError as exc:
        logger.error("Flow failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error in flow.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected automation error occurred.",
        )
    finally:
        del payload
    return result


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_200_OK)
async def webhook_register(
    payload: RegisterPatientPayload,
    x_webhook_secret: str = Header(..., alias="X-Webhook-Secret"),
):
    """Register a new or existing patient in EPOWERdoc."""
    _verify_secret(x_webhook_secret)
    logger.info("Register patient webhook received.")
    return await _run_flow(register_patient_flow.run, payload)


@router.post("/print-labels", status_code=status.HTTP_200_OK)
async def webhook_print_labels(
    payload: PrintLabelsPayload,
    x_webhook_secret: str = Header(..., alias="X-Webhook-Secret"),
):
    """Select a patient on the EPD main screen to begin the print labels flow."""
    _verify_secret(x_webhook_secret)
    logger.info("Print labels webhook received.")
    return await _run_flow(print_labels_flow.run, payload)
