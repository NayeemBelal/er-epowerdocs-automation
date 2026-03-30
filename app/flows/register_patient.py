"""
flows/register_patient.py — Patient registration flow.

Covers both new and existing patients:
  1. Click ADD Patient on the main screen
  2. Fill Last Name, First Name, DOB, Gender in Patient Search
  3. If an existing patient appears in results → select them
     Otherwise → click New Patient
  4. Fill cell number on the Registration screen
  5. Save and Close

HIPAA: no PHI values appear in any log call.
"""

import logging
import time
from pywinauto import Application, timings
from pywinauto.timings import TimeoutError as PWTimeoutError

from app.config import settings
from app.models.register_patient import RegisterPatientPayload
from app.shared.epd_connect import connect_to_epower

logger = logging.getLogger(__name__)


# ── Step helpers ──────────────────────────────────────────────────────────────

def _open_add_patient(app: Application):
    """Click ADD Patient and return the Patient Search window."""
    try:
        main_win = app.window(auto_id="frmMain")
        main_win.set_focus()
        add_btn = main_win.child_window(auto_id="PNGeneral").child_window(
            auto_id="L1", control_type="Text"
        )
        add_btn.wait("visible", timeout=settings.ui_timeout)
        add_btn.click_input()
        logger.info("ADD Patient clicked.")
    except PWTimeoutError:
        logger.error("ADD Patient control not found.")
        raise RuntimeError("Could not locate ADD Patient button on main screen.")

    try:
        main_win = app.window(auto_id="frmMain")
        search_win = main_win.child_window(auto_id="frmPatientSearch", control_type="Window")
        search_win.wait("visible", timeout=settings.ui_timeout)
        logger.info("Patient Search window visible.")
        return search_win
    except PWTimeoutError:
        logger.error("Patient Search window did not appear.")
        raise RuntimeError("Patient Search window did not open in time.")


def _fill_pane_edit(parent, pane_auto_id: str, value: str, label: str) -> None:
    """Type into an Edit nested inside a named Pane — the standard pattern on this form."""
    try:
        edit = parent.child_window(
            auto_id=pane_auto_id, control_type="Pane"
        ).child_window(auto_id="TextBox1", control_type="Edit")
        edit.wait("visible enabled", timeout=settings.ui_timeout)
        edit.set_edit_text("")
        edit.type_keys(value, with_spaces=True)
        logger.info("Filled %s.", label)
    except PWTimeoutError:
        logger.error("Timed out on %s.", label)
        raise RuntimeError(f"UI control not found: {label}")
    except Exception:
        logger.error("Error filling %s.", label)
        raise RuntimeError(f"Failed to fill UI control: {label}")


def _inject_search_fields(search_win, payload: RegisterPatientPayload) -> None:
    """Populate Last Name, First Name, DOB, and Gender in the Patient Search form."""
    year, month, day = payload.dob.split("-")

    _fill_pane_edit(search_win, "txtLastName",  payload.last_name,  "last_name")
    _fill_pane_edit(search_win, "txtFirstName", payload.first_name, "first_name")
    _fill_pane_edit(search_win, "txtMonth",     month,              "dob_month")
    _fill_pane_edit(search_win, "txtDay",       day,                "dob_day")
    _fill_pane_edit(search_win, "txtYear",      year,               "dob_year")

    gender_id = "rbM" if payload.gender == "M" else "rbF"
    try:
        btn = search_win.child_window(auto_id=gender_id, control_type="RadioButton")
        btn.wait("visible enabled", timeout=settings.ui_timeout)
        btn.click_input()
        logger.info("Gender selected.")
    except PWTimeoutError:
        logger.error("Gender radio button not found.")
        raise RuntimeError("Gender radio button unavailable.")

    logger.info("Search fields injected.")


def _select_existing_or_new(search_win) -> bool:
    """
    Wait for EPD's auto-search, then:
    - If a patient row appears (lLName0) → click it → return True
    - Otherwise → click New Patient → return False
    """
    time.sleep(1.5)

    results_pane = search_win.child_window(auto_id="pn1", control_type="Pane")
    try:
        first_result = results_pane.child_window(auto_id="lLName0", control_type="Text")
        first_result.wait("visible", timeout=2)
        first_result.click_input()
        logger.info("Existing patient row selected.")
        return True
    except PWTimeoutError:
        logger.info("No existing patient found — proceeding to New Patient.")

    try:
        new_pt_btn = search_win.child_window(auto_id="cmdAddVisit", control_type="Button")
        new_pt_btn.wait("visible enabled", timeout=settings.ui_timeout)
        new_pt_btn.click_input()
        logger.info("New Patient clicked.")
        return False
    except PWTimeoutError:
        logger.error("New Patient button unavailable.")
        raise RuntimeError("New Patient button not found or not enabled.")


def _fill_registration_screen(search_win, payload: RegisterPatientPayload) -> None:
    """Fill cell number on the Registration screen and click Save and Close."""
    try:
        reg_win = search_win.child_window(auto_id="frmRegistration", control_type="Window")
        reg_win.wait("visible", timeout=settings.ui_timeout)
        logger.info("Registration screen visible.")
    except PWTimeoutError:
        logger.error("Registration screen did not appear.")
        raise RuntimeError("Registration screen did not open in time.")

    try:
        no_cell_chk = reg_win.child_window(auto_id="chkNoCellPhone", control_type="CheckBox")
        no_cell_chk.wait("visible", timeout=settings.ui_timeout)
        if no_cell_chk.get_toggle_state() == 1:
            no_cell_chk.click_input()
            logger.info("Unchecked 'No cell phone number'.")
    except PWTimeoutError:
        logger.warning("'No cell phone number' checkbox not found — skipping.")

    try:
        cell_edit = reg_win.child_window(auto_id="txtCell", control_type="Edit")
        cell_edit.wait("visible enabled", timeout=settings.ui_timeout)
        cell_edit.set_edit_text("")
        cell_edit.type_keys(payload.cell_number, with_spaces=True)
        logger.info("Cell number filled.")
    except PWTimeoutError:
        logger.error("Cell number field not found.")
        raise RuntimeError("Cell number field unavailable.")

    try:
        save_btn = reg_win.child_window(auto_id="btnSaveClose", control_type="Button")
        save_btn.wait("visible enabled", timeout=settings.ui_timeout)
        save_btn.click_input()
        logger.info("Save and Close clicked.")
    except PWTimeoutError:
        logger.error("Save and Close button not found.")
        raise RuntimeError("Save and Close button unavailable.")


# ── Public entry point ────────────────────────────────────────────────────────

def run(payload: RegisterPatientPayload) -> dict:
    """
    Execute the full patient registration flow.
    Called by the router via run_in_executor.
    Returns {"status": "success"} or raises RuntimeError (no PHI in message).
    """
    logger.info("Register patient flow started.")
    timings.Timings.fast()

    app = connect_to_epower()
    search_win = _open_add_patient(app)
    _inject_search_fields(search_win, payload)
    _select_existing_or_new(search_win)
    _fill_registration_screen(search_win, payload)

    logger.info("Register patient flow completed.")
    return {"status": "success"}
