"""
flows/print_labels.py — Print registration labels flow.

Step 1: Click the correct patient row on the EPD main tracking screen.

The main screen (frmMain → PNGeneral → dgvTracking) shows a DataGridView
of current patients. Each row's patient name cell has a stable title of
"Pt Name Row N" (N = 0, 1, 2, ...). We iterate rows until we find one
whose displayed text matches the requested patient, then click it.

EPD displays names in "LAST, FIRST" format. Matching is case-insensitive.

HIPAA: no PHI values appear in any log call.
"""

import logging
from pywinauto import Application
from pywinauto.timings import TimeoutError as PWTimeoutError

from app.config import settings
from app.models.print_labels import PrintLabelsPayload
from app.shared.epd_connect import connect_to_epower

logger = logging.getLogger(__name__)

# Maximum number of patient rows to scan in the tracking grid.
_MAX_ROWS = 50


def _click_patient_row(app: Application, payload: PrintLabelsPayload) -> None:
    """
    Locate the patient in the dgvTracking grid and click their name cell.
    Raises RuntimeError if the patient is not found.
    """
    try:
        main_win = app.window(auto_id="frmMain")
        logger.info("frmMain window wrapper created.")
        main_win.set_focus()
        logger.info("frmMain focused.")
        grid = main_win.child_window(auto_id="dgvTracking", control_type="Table")
        logger.info("dgvTracking wrapper created, waiting for visible...")
        grid.wait("visible", timeout=settings.ui_timeout)
        logger.info("Tracking grid located and visible.")
    except PWTimeoutError:
        logger.error("Tracking grid not found — dgvTracking did not become visible within timeout.")
        raise RuntimeError("Could not locate patient tracking grid on main screen.")

    # EPD displays names as "LAST, F" (last name + first initial, no period).
    target = f"{payload.last_name}, {payload.first_name[0]}".upper()
    logger.info("Target name length: %d, contains comma: %s", len(target), "," in target)

    for row_index in range(_MAX_ROWS):
        cell_title = f"Pt Name Row {row_index}"
        try:
            cell = grid.child_window(title=cell_title, control_type="Edit")
            cell.wait("exists", timeout=1)
        except PWTimeoutError:
            logger.info("No cell found at row %d — end of patient list (%d rows scanned).", row_index, row_index)
            break

        cell_text = cell.window_text().strip().upper()
        logger.info(
            "Row %d: cell_text length=%d, target length=%d, match=%s",
            row_index, len(cell_text), len(target), cell_text == target,
        )
        if cell_text == target:
            cell.click_input()
            logger.info("Patient row clicked at row %d.", row_index)
            return

    logger.error("Patient not found after scanning %d rows.", min(row_index + 1, _MAX_ROWS))
    raise RuntimeError("Patient not found in the EPD tracking grid.")


# ── Public entry point ────────────────────────────────────────────────────────

def run(payload: PrintLabelsPayload) -> dict:
    """
    Execute the print labels flow.
    Called by the router via run_in_executor.
    Returns {"status": "success"} or raises RuntimeError (no PHI in message).
    """
    logger.info("Print labels flow started.")

    app = connect_to_epower()
    _click_patient_row(app, payload)

    logger.info("Print labels flow: patient selected.")
    return {"status": "success"}
