"""
main.py — Application entry point.

Responsibilities:
  - Configure logging
  - Create the FastAPI app
  - Mount routers
  - Start Uvicorn

All business logic lives in app/flows/, app/models/, and app/routers/.
"""

import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.config import settings
from app.routers.webhook import router as webhook_router


# ── Logging (metadata only — no PHI) ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    # FileHandler intentionally excluded: log files could persist PHI.
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("EPOWERdoc automation server starting up.")
    yield
    logger.info("EPOWERdoc automation server shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="EPOWERdoc Automation Bridge",
    version="0.2.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.include_router(webhook_router)


@app.get("/health", status_code=200)
async def health_check():
    return {"status": "ok"}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        access_log=False,
    )
