"""
epower_hook.py — pywinauto automation layer for EPOWERdoc.

HIPAA compliance rules for this module:
  - Logger calls must NEVER include payload field values (names, DOB, IDs).
  - No payload data may be written to disk, temp files, or the clipboard
    beyond what pywinauto type-writes directly into the target control.
  - All exceptions re-raised to the caller must carry only metadata messages.
"""

import logging
from pywinauto import Application
from pywinauto.timings import TimeoutError as PWTimeoutError

from app.models import PatientPayload
from app.config import settings

logger = logging.getLogger(__name__)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _connect_to_epower() -> Application:
    """Connect to the already-running EPD.exe process via the UIA backend."""
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


def _open_add_patient(app: Application):
    """
    Click the 'ADD Patient' link on the main Frisco Registration panel.
    Returns the Patient Search window wrapper.
    """
    try:
        main_win = app.window(auto_id="frmMain")
        main_win.set_focus()

        # Click the 'ADD Patient' static text link in the registration panel
        add_btn = main_win.child_window(auto_id="PNGeneral").child_window(
            auto_id="L1", control_type="Text"
        )
        add_btn.wait("visible", timeout=settings.ui_timeout)
        add_btn.click_input()
        logger.info("ADD Patient clicked.")
    except PWTimeoutError:
        logger.error("ADD Patient control not found on main screen.")
        raise RuntimeError("Could not locate ADD Patient button on main screen.")

    try:
        main_win = app.window(auto_id="frmMain")
        search_win = main_win.child_window(auto_id="frmPatientSearch", control_type="Window")
        search_win.wait("visible", timeout=settings.ui_timeout)
        logger.info("Patient Search window is visible.")
        return search_win
    except PWTimeoutError:
        logger.error("Patient Search window did not appear.")
        raise RuntimeError("Patient Search window did not open in time.")


def _fill_edit(parent_win, pane_auto_id: str, value: str, label: str) -> None:
    """
    Helper: locate a field by its parent Pane auto_id, then type into the
    inner Edit control (all text fields in this form follow this pattern).
    """
    try:
        edit = parent_win.child_window(
            auto_id=pane_auto_id, control_type="Pane"
        ).child_window(auto_id="TextBox1", control_type="Edit")
        edit.wait("visible enabled", timeout=settings.ui_timeout)
        edit.set_edit_text("")
        edit.type_keys(value, with_spaces=True)
        logger.info("Filled %s field.", label)
    except PWTimeoutError:
        logger.error("Timed out locating %s field.", label)
        raise RuntimeError(f"UI control not found: {label}")
    except Exception:
        logger.error("Error filling %s field.", label)
        raise RuntimeError(f"Failed to fill UI control: {label}")


def _inject_patient_data(search_win, payload: PatientPayload) -> None:
    """
    Fill all patient fields in the Patient Search / New Patient form.
    DOB is split into separate month/day/year controls (mm/dd/yyyy).
    HIPAA: no field values are logged — only field-level metadata.
    """
    # Parse DOB from YYYY-MM-DD → separate month, day, year strings
    year, month, day = payload.dob.split("-")

    _fill_edit(search_win, "txtLastName",  payload.last_name,  "last_name")
    _fill_edit(search_win, "txtFirstName", payload.first_name, "first_name")
    _fill_edit(search_win, "txtMonth",     month,              "dob_month")
    _fill_edit(search_win, "txtDay",       day,                "dob_day")
    _fill_edit(search_win, "txtYear",      year,               "dob_year")

    # Select gender radio button (M or F)
    gender_auto_id = "rbM" if payload.gender == "M" else "rbF"
    try:
        gender_btn = search_win.child_window(auto_id=gender_auto_id, control_type="RadioButton")
        gender_btn.wait("visible enabled", timeout=settings.ui_timeout)
        gender_btn.click_input()
        logger.info("Gender radio button selected.")
    except PWTimeoutError:
        logger.error("Gender radio button not found.")
        raise RuntimeError("Gender radio button unavailable.")

    logger.info("All patient fields injected.")


def _click_new_patient(search_win) -> None:
    """Click the 'New Patient' button to submit the registration."""
    try:
        new_pt_btn = search_win.child_window(
            auto_id="cmdAddVisit", control_type="Button"
        )
        new_pt_btn.wait("visible enabled", timeout=settings.ui_timeout)
        new_pt_btn.click_input()
        logger.info("New Patient button clicked.")
    except PWTimeoutError:
        logger.error("New Patient button not found or not enabled.")
        raise RuntimeError("New Patient button unavailable.")


def _fill_registration_screen(search_win, payload: PatientPayload) -> None:
    """
    Fill the Registration screen that opens after clicking New Patient.
    Enters cell number, then clicks Save and Close.
    """
    try:
        reg_win = search_win.child_window(auto_id="frmRegistration", control_type="Window")
        reg_win.wait("visible", timeout=settings.ui_timeout)
        logger.info("Registration screen is visible.")
    except PWTimeoutError:
        logger.error("Registration screen did not appear.")
        raise RuntimeError("Registration screen did not open in time.")

    # Uncheck 'No cell phone number' if it is checked, so the field is enabled
    try:
        no_cell_chk = reg_win.child_window(auto_id="chkNoCellPhone", control_type="CheckBox")
        no_cell_chk.wait("visible", timeout=settings.ui_timeout)
        if no_cell_chk.get_toggle_state() == 1:
            no_cell_chk.click_input()
            logger.info("Unchecked 'No cell phone number'.")
    except PWTimeoutError:
        logger.warning("'No cell phone number' checkbox not found — skipping.")

    # Fill cell number
    try:
        cell_edit = reg_win.child_window(auto_id="txtCell", control_type="Edit")
        cell_edit.wait("visible enabled", timeout=settings.ui_timeout)
        cell_edit.set_edit_text("")
        cell_edit.type_keys(payload.cell_number, with_spaces=True)
        logger.info("Cell number field filled.")
    except PWTimeoutError:
        logger.error("Cell number field not found.")
        raise RuntimeError("Cell number field unavailable.")

    # Save and Close
    try:
        save_btn = reg_win.child_window(auto_id="btnSaveClose", control_type="Button")
        save_btn.wait("visible enabled", timeout=settings.ui_timeout)
        save_btn.click_input()
        logger.info("Save and Close clicked.")
    except PWTimeoutError:
        logger.error("Save and Close button not found.")
        raise RuntimeError("Save and Close button unavailable.")


# ── Public orchestrator ───────────────────────────────────────────────────────

def register_patient(payload: PatientPayload) -> dict:
    """
    Full registration workflow:
      connect → open Add Patient → fill fields → click New Patient.

    Returns {"status": "success"} or raises RuntimeError (metadata only, no PHI).
    Called from main.py inside asyncio.run_in_executor.
    """
    logger.info("Registration workflow started.")

    app = _connect_to_epower()
    search_win = _open_add_patient(app)
    _inject_patient_data(search_win, payload)
    _click_new_patient(search_win)
    _fill_registration_screen(search_win, payload)

    logger.info("Registration workflow completed — patient saved.")
    return {"status": "success"}
