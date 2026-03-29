"""
shared/epd_connect.py — Shared EPD process connection.

Every flow imports _connect_to_epower() from here so the connection
logic is never duplicated across flows.
"""

import logging
from pywinauto import Application
from pywinauto.timings import TimeoutError as PWTimeoutError

from app.config import settings

logger = logging.getLogger(__name__)


def connect_to_epower() -> Application:
    """
    Connect to the already-running EPD.exe process via the UIA backend.
    Raises RuntimeError if the process is not found.
    """
    try:
        app = Application(backend="uia").connect(
            path=settings.epower_process_name,
            timeout=settings.ui_timeout,
        )
        logger.info("EPD process connected.")
        return app
    except Exception:
        logger.error("Failed to connect to EPD process.")
        raise RuntimeError("EPD.exe process not found. Ensure EPOWERdoc is running.")
