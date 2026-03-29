"""
flows/input_demographics.py — Input demographics flow.

1. Click the correct patient row on the EPD main tracking screen.
2. In the Patient Menu (frmPatMenu), click Demographics.

HIPAA: no PHI values appear in any log call.
"""

import logging

from pywinauto import Application
from pywinauto.timings import TimeoutError as PWTimeoutError

from app.config import settings
from app.models.input_demographics import InputDemographicsPayload
from app.shared.epd_connect import connect_to_epower

logger = logging.getLogger(__name__)

_MAX_ROWS = 50


def _click_patient_row(app: Application, payload: InputDemographicsPayload) -> None:
    """
    Locate the patient in the dgvTracking grid and click their name cell.
    Raises RuntimeError if the patient is not found.
    """
    try:
        main_win = app.window(auto_id="frmMain")
        main_win.set_focus()
        grid = main_win.child_window(auto_id="dgvTracking", control_type="Table")
        grid.wait("visible", timeout=settings.ui_timeout)
        logger.info("Tracking grid located and visible.")
    except PWTimeoutError:
        logger.error("Tracking grid not found — dgvTracking did not become visible within timeout.")
        raise RuntimeError("Could not locate patient tracking grid on main screen.")

    # EPD displays names as "LAST, F" (last name + first initial, no period).
    target = f"{payload.last_name}, {payload.first_name[0]}".upper()

    for row_index in range(_MAX_ROWS):
        cell_title = f"Pt Name Row {row_index}"
        try:
            cell = grid.child_window(title=cell_title, control_type="Edit")
            cell.wait("exists", timeout=1)
        except PWTimeoutError:
            logger.info("End of patient list — %d rows scanned.", row_index)
            break

        cell_text = cell.get_value().strip().upper()
        if cell_text == target:
            cell.click_input()
            logger.info("Patient row clicked.")
            return

    logger.error("Patient not found after scanning %d rows.", min(row_index + 1, _MAX_ROWS))
    raise RuntimeError("Patient not found in the EPD tracking grid.")


def _click_demographics(app: Application) -> None:
    """
    In the Patient Menu, click the Demographics button.
    """
    try:
        main_win = app.window(auto_id="frmMain")
        pat_menu = main_win.child_window(auto_id="frmPatMenu", control_type="Window")
        pat_menu.wait("visible", timeout=settings.ui_timeout)
        logger.info("Patient Menu visible.")
    except PWTimeoutError:
        logger.error("Patient Menu did not appear.")
        raise RuntimeError("Patient Menu did not open after selecting patient.")

    try:
        demo_btn = pat_menu.child_window(auto_id="cmdDemographics", control_type="Button")
        demo_btn.wait("visible enabled", timeout=settings.ui_timeout)
        demo_btn.click_input()
        logger.info("Demographics clicked.")
    except PWTimeoutError:
        logger.error("Demographics button not found.")
        raise RuntimeError("Demographics button unavailable in Patient Menu.")


# ── Public entry point ────────────────────────────────────────────────────────

def run(payload: InputDemographicsPayload) -> dict:
    """
    Execute the input demographics flow.
    Called by the router via run_in_executor.
    Returns {"status": "success"} or raises RuntimeError (no PHI in message).
    """
    logger.info("Input demographics flow started.")

    app = connect_to_epower()
    _click_patient_row(app, payload)
    _click_demographics(app)

    logger.info("Input demographics flow completed.")
    return {"status": "success"}
