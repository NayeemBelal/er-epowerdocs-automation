"""
flows/input_demographics.py — Input demographics flow.

1. Click the correct patient row on the EPD main tracking screen.
2. In the Patient Menu (frmPatMenu), click Demographics.
3. In the Registration screen (frmRegistration / gbPatient), fill all
   demographic fields and click Save and Close.

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_edit(parent, auto_id: str, value: str, field_name: str) -> None:
    """Set the text of an Edit control. Skips silently if value is falsy."""
    if not value:
        return
    try:
        field = parent.child_window(auto_id=auto_id, control_type="Edit")
        field.wait("visible enabled", timeout=settings.ui_timeout)
        field.set_edit_text(value.upper())
        logger.info("Edit set: %s", field_name)
    except PWTimeoutError:
        logger.error("Edit field not found: %s", field_name)
        raise RuntimeError(f"{field_name} field unavailable in Registration screen.")


def _set_combo(parent, auto_id: str, value: str, field_name: str) -> None:
    """Expand a ComboBox and click the matching ListItem."""
    if not value:
        return
    try:
        combo = parent.child_window(auto_id=auto_id, control_type="ComboBox")
        combo.wait("visible enabled", timeout=settings.ui_timeout)
        combo.click_input()
        combo.child_window(title=value, control_type="ListItem").click_input()
        logger.info("ComboBox set: %s", field_name)
    except PWTimeoutError:
        logger.error("ComboBox or option not found: %s", field_name)
        raise RuntimeError(f"{field_name} option unavailable in Registration screen.")


def _set_list(parent, auto_id: str, value: str, field_name: str) -> None:
    """Select an item in a ListBox control by text."""
    if not value:
        return
    try:
        list_box = parent.child_window(auto_id=auto_id, control_type="List")
        list_box.wait("visible", timeout=settings.ui_timeout)
        list_box.select(value)
        logger.info("ListBox set: %s", field_name)
    except PWTimeoutError:
        logger.error("ListBox not found: %s", field_name)
        raise RuntimeError(f"{field_name} ListBox unavailable in Registration screen.")
    except Exception:
        logger.exception("Failed to select item in ListBox: %s", field_name)
        raise RuntimeError(f"Could not select {field_name} — verify option name matches exactly.")


# ── Flow steps ────────────────────────────────────────────────────────────────

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
    """In the Patient Menu, click the Demographics button."""
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


def _fill_demographics(app: Application, payload: InputDemographicsPayload) -> None:
    """
    In the Registration screen, fill all demographic fields on the
    Patient Information tab and click Save and Close.
    """
    try:
        main_win = app.window(auto_id="frmMain")
        reg_win = main_win.child_window(auto_id="frmRegistration", control_type="Window")
        reg_win.wait("visible", timeout=settings.ui_timeout)
        logger.info("Registration screen visible.")
    except PWTimeoutError:
        logger.error("Registration screen did not appear after clicking Demographics.")
        raise RuntimeError("Registration screen did not open.")

    pat_info = reg_win.child_window(auto_id="gbPatient", control_type="Group")

    # Address
    _set_edit(pat_info, "txtAdd1",  payload.address,  "address")
    _set_edit(pat_info, "txtCity",  payload.city,     "city")
    _set_edit(pat_info, "txtState", payload.state,    "state")
    _set_edit(pat_info, "txtZip",   payload.zip_code, "zip")

    # Contact
    _set_edit(pat_info, "txtEmail", payload.email, "email")

    # SSN — always written; defaults to 000000000
    _set_edit(pat_info, "txtSSN", payload.ssn, "SSN")

    # Dropdowns with defaults
    _set_combo(pat_info, "cbMarital",           payload.marital_status,    "marital status")
    _set_combo(pat_info, "cbEmployment",         payload.employment_status, "employment status")
    _set_combo(pat_info, "cbReligion",           payload.religion,          "religion")
    _set_combo(pat_info, "cbPreferredLanguage",  payload.preferred_language, "preferred language")
    _set_combo(pat_info, "cbEtnicity",           payload.ethnicity,         "ethnicity")

    # Race — ListBox, not ComboBox
    _set_list(pat_info, "LstRace", payload.race, "race")

    # How did you hear about us — free-text input inside a ComboBox, optional
    if payload.how_did_you_hear:
        try:
            combo = pat_info.child_window(auto_id="cbAboutUsSource", control_type="ComboBox")
            combo.wait("visible enabled", timeout=settings.ui_timeout)
            edit = combo.child_window(auto_id="1001", control_type="Edit")
            edit.set_edit_text(payload.how_did_you_hear.upper())
            logger.info("How did you hear about us set.")
        except PWTimeoutError:
            logger.error("How did you hear about us field not found.")
            raise RuntimeError("How did you hear about us field unavailable in Registration screen.")

    # Save and Close
    try:
        save_btn = reg_win.child_window(auto_id="btnSaveClose", control_type="Button")
        save_btn.wait("visible enabled", timeout=settings.ui_timeout)
        save_btn.click_input()
        logger.info("Save and Close clicked.")
    except PWTimeoutError:
        logger.error("Save and Close button not found.")
        raise RuntimeError("Save and Close button unavailable on Registration screen.")


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
    _fill_demographics(app, payload)

    logger.info("Input demographics flow completed.")
    return {"status": "success"}
