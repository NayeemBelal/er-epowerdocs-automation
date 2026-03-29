"""
flows/print_labels.py — Print registration labels flow.

1. Click the correct patient row on the EPD main tracking screen.
2. In the Patient Menu (frmPatMenu), check Registration Labels.
3. Click View.

HIPAA: no PHI values appear in any log call.
"""

import logging
from pathlib import Path

import yaml
from pywinauto import Application
from pywinauto.timings import TimeoutError as PWTimeoutError

from app.config import settings
from app.models.print_labels import PrintLabelsPayload
from app.shared.epd_connect import connect_to_epower

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


def _load_provider_name() -> str:
    """Load the selected provider name from config.yaml."""
    with open(_CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f)
    names = cfg["providers"]["names"]
    index = cfg["providers"]["selected_index"]
    return names[index]

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


def _select_registration_labels(app: Application) -> None:
    """
    In the Patient Menu, check Registration Labels then click View.
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
        chk = pat_menu.child_window(auto_id="cbRegistrationLabels", control_type="CheckBox")
        chk.wait("visible enabled", timeout=settings.ui_timeout)
        if chk.get_toggle_state() != 1:
            chk.click_input()
        logger.info("Registration Labels checked.")
    except PWTimeoutError:
        logger.error("Registration Labels checkbox not found.")
        raise RuntimeError("Registration Labels checkbox unavailable.")

    try:
        view_btn = pat_menu.child_window(auto_id="cmdPreview", control_type="Button")
        view_btn.wait("visible enabled", timeout=settings.ui_timeout)
        view_btn.click_input()
        logger.info("View clicked.")
    except PWTimeoutError:
        logger.error("View button not found.")
        raise RuntimeError("View button unavailable.")


def _fill_provider_name(app: Application, provider_name: str) -> None:
    """
    In the Add Provider dialog (frmInputBox), type the provider name and click Record.
    """
    try:
        main_win = app.window(auto_id="frmMain")
        add_provider_win = main_win.child_window(auto_id="frmInputBox", control_type="Window")
        add_provider_win.wait("visible", timeout=settings.ui_timeout)
        logger.info("Add Provider dialog visible.")
    except PWTimeoutError:
        logger.error("Add Provider dialog did not appear.")
        raise RuntimeError("Add Provider dialog did not open after clicking View.")

    try:
        text_box = add_provider_win.child_window(auto_id="TextBox1", control_type="Edit")
        text_box.wait("visible enabled", timeout=settings.ui_timeout)
        text_box.set_edit_text("")
        text_box.type_keys(provider_name, with_spaces=True)
        logger.info("Provider name typed.")
    except PWTimeoutError:
        logger.error("Provider name text box not found.")
        raise RuntimeError("Provider name input unavailable.")

    try:
        record_btn = add_provider_win.child_window(auto_id="btnOk", control_type="Button")
        record_btn.wait("visible enabled", timeout=settings.ui_timeout)
        record_btn.click_input()
        logger.info("Record clicked.")
    except PWTimeoutError:
        logger.error("Record button not found.")
        raise RuntimeError("Record button unavailable.")


def _click_print_icon(app: Application) -> None:
    """
    In the Document Viewer (frmTemplatePreview), click the Print toolbar icon.
    """
    try:
        main_win = app.window(auto_id="frmMain")
        viewer = main_win.child_window(auto_id="frmTemplatePreview", control_type="Window")
        viewer.wait("visible", timeout=settings.ui_timeout)
        logger.info("Document Viewer visible.")
    except PWTimeoutError:
        logger.error("Document Viewer did not appear.")
        raise RuntimeError("Document Viewer did not open after clicking View.")

    try:
        toolbar = viewer.child_window(auto_id="mainToolstrip", control_type="ToolBar")
        print_btn = toolbar.child_window(title="Print", control_type="Button")
        print_btn.wait("visible enabled", timeout=settings.ui_timeout)
        print_btn.click_input()
        logger.info("Print icon clicked.")
    except PWTimeoutError:
        logger.error("Print icon not found in toolbar.")
        raise RuntimeError("Print icon unavailable in Document Viewer toolbar.")


# ── Public entry point ────────────────────────────────────────────────────────

def run(payload: PrintLabelsPayload) -> dict:
    """
    Execute the print labels flow.
    Called by the router via run_in_executor.
    Returns {"status": "success"} or raises RuntimeError (no PHI in message).
    """
    logger.info("Print labels flow started.")

    provider_name = _load_provider_name()
    logger.info("Provider loaded from config.")

    app = connect_to_epower()
    _click_patient_row(app, payload)
    _select_registration_labels(app)
    _fill_provider_name(app, provider_name)
    _click_print_icon(app)

    logger.info("Print labels flow completed.")
    return {"status": "success"}
