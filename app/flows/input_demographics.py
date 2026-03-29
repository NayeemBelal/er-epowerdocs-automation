"""
flows/input_demographics.py — Input demographics flow.

1. Click the correct patient row on the EPD main tracking screen.
2. In the Patient Menu (frmPatMenu), click Demographics.
3. In the Registration screen (frmRegistration / gbPatient), fill all
   demographic fields and click Save and Close.

HIPAA: no PHI values appear in any log call.
"""

import logging

from pywinauto import Application, timings
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
        parent.child_window(auto_id=auto_id, control_type="Edit").set_edit_text(value.upper())
        logger.info("Edit set: %s", field_name)
    except Exception:
        logger.error("Edit field not found: %s", field_name)
        raise RuntimeError(f"{field_name} field unavailable in Registration screen.")


def _set_combo(parent, auto_id: str, value: str, field_name: str) -> None:
    """Expand a ComboBox and click the matching ListItem."""
    if not value:
        return
    try:
        combo = parent.child_window(auto_id=auto_id, control_type="ComboBox")
        combo.click_input()
        combo.child_window(title=value, control_type="ListItem").click_input()
        logger.info("ComboBox set: %s", field_name)
    except Exception:
        logger.error("ComboBox or option not found: %s", field_name)
        raise RuntimeError(f"{field_name} option unavailable in Registration screen.")


def _set_list(parent, auto_id: str, value: str, field_name: str) -> None:
    """Select an item in a ListBox control by text."""
    if not value:
        return
    try:
        list_box = parent.child_window(auto_id=auto_id, control_type="List")
        list_box.set_focus()
        list_box.child_window(title=value, control_type="ListItem").click_input()
        logger.info("ListBox set: %s", field_name)
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
    _set_combo(pat_info, "cbEmployment", "Employed" if payload.employer_name else "Unknown", "employment status")
    _set_combo(pat_info, "cbReligion",           payload.religion,          "religion")
    _set_combo(pat_info, "cbPreferredLanguage",  payload.preferred_language, "preferred language")
    _set_combo(pat_info, "cbEtnicity",           payload.ethnicity,         "ethnicity")

    # Race — ListBox, not ComboBox
    _set_list(pat_info, "LstRace", payload.race, "race")

    # How did you hear about us — free-text input inside a ComboBox, optional
    if payload.how_did_you_hear:
        try:
            combo = pat_info.child_window(auto_id="cbAboutUsSource", control_type="ComboBox")
            edit = combo.child_window(auto_id="1001", control_type="Edit")
            edit.set_edit_text(payload.how_did_you_hear.upper())
            logger.info("How did you hear about us set.")
        except Exception:
            logger.error("How did you hear about us field not found.")
            raise RuntimeError("How did you hear about us field unavailable in Registration screen.")


def _fill_guarantor(app: Application, payload: InputDemographicsPayload) -> None:
    """
    Fill the Guarantor/Responsible section.
    - Adult (no guardian names): check Same as Patient.
    - Minor (guardian names provided): fill Last/First, check Same address + Same phones.
    """
    main_win = app.window(auto_id="frmMain")
    reg_win = main_win.child_window(auto_id="frmRegistration", control_type="Window")
    guarantor = reg_win.child_window(auto_id="GroupBox1", control_type="Group")

    is_minor = bool(payload.guardian_first_name and payload.guardian_last_name)

    if not is_minor:
        try:
            chk = guarantor.child_window(auto_id="ckGSameAsPatient", control_type="CheckBox")
            if chk.get_toggle_state() != 1:
                chk.click_input()
            logger.info("Guarantor: Same as Patient checked.")
        except Exception:
            logger.error("Same as Patient checkbox not found.")
            raise RuntimeError("Same as Patient checkbox unavailable.")
    else:
        try:
            guarantor.child_window(auto_id="txtGLast",  control_type="Edit").set_edit_text(payload.guardian_last_name.upper())
            guarantor.child_window(auto_id="txtGFirst", control_type="Edit").set_edit_text(payload.guardian_first_name.upper())
            logger.info("Guarantor name filled.")
        except Exception:
            logger.error("Guarantor name fields not found.")
            raise RuntimeError("Guarantor name fields unavailable.")

        try:
            chk_addr = guarantor.child_window(auto_id="ckGSameAddress", control_type="CheckBox")
            if chk_addr.get_toggle_state() != 1:
                chk_addr.click_input()
            logger.info("Guarantor: Same address checked.")
        except Exception:
            logger.error("Same address checkbox not found.")
            raise RuntimeError("Same address checkbox unavailable.")

        try:
            chk_phones = guarantor.child_window(auto_id="ckGSamePhones", control_type="CheckBox")
            if chk_phones.get_toggle_state() != 1:
                chk_phones.click_input()
            logger.info("Guarantor: Same phones checked.")
        except Exception:
            logger.error("Same phones checkbox not found.")
            raise RuntimeError("Same phones checkbox unavailable.")


def _fill_employer_tab(app: Application, payload: InputDemographicsPayload) -> None:
    """Click the Employer tab and fill in the Employer Name field."""
    if not payload.employer_name:
        return

    try:
        main_win = app.window(auto_id="frmMain")
        reg_win = main_win.child_window(auto_id="frmRegistration", control_type="Window")
        reg_win.child_window(title="Employer", control_type="TabItem").click_input()
        logger.info("Employer tab clicked.")
    except Exception:
        logger.error("Employer tab not found.")
        raise RuntimeError("Employer tab unavailable on Registration screen.")

    try:
        main_win = app.window(auto_id="frmMain")
        reg_win = main_win.child_window(auto_id="frmRegistration", control_type="Window")
        emp_pane = reg_win.child_window(auto_id="tbEmp", control_type="Pane")
        emp_pane.child_window(auto_id="txtEmpName", control_type="Edit").set_edit_text(payload.employer_name.upper())
        logger.info("Employer name filled.")
    except Exception:
        logger.error("Employer Name field not found.")
        raise RuntimeError("Employer Name field unavailable on Employer tab.")


def _fill_primary_ins_tab(app: Application, payload: InputDemographicsPayload) -> None:
    """
    Click the Primary Ins. tab and fill the Insured + Insurance sections.
    Skipped entirely if ins_name is not provided.
    """
    if not payload.ins_name:
        return

    try:
        main_win = app.window(auto_id="frmMain")
        reg_win = main_win.child_window(auto_id="frmRegistration", control_type="Window")
        reg_win.child_window(title="Primary Ins.", control_type="TabItem").click_input()
        logger.info("Primary Ins. tab clicked.")
    except Exception:
        logger.error("Primary Ins. tab not found.")
        raise RuntimeError("Primary Ins. tab unavailable on Registration screen.")

    main_win = app.window(auto_id="frmMain")
    reg_win = main_win.child_window(auto_id="frmRegistration", control_type="Window")
    pane = reg_win.child_window(auto_id="tbPri", control_type="Pane")

    # Insured section — Same as Patient (adult) or Same as Guarantor (minor)
    is_minor = bool(payload.guardian_first_name and payload.guardian_last_name)
    insured = pane.child_window(auto_id="GroupBox3", control_type="Group")
    chk_id = "ck1SameAsGuarantor" if is_minor else "ck1SameAsPatient"
    chk_name = "Same as Guarantor" if is_minor else "Same as Patient"
    try:
        chk = insured.child_window(auto_id=chk_id, control_type="CheckBox")
        if chk.get_toggle_state() != 1:
            chk.click_input()
        logger.info("Insured: %s checked.", chk_name)
    except Exception:
        logger.error("Insured checkbox not found: %s", chk_name)
        raise RuntimeError(f"{chk_name} checkbox unavailable on Primary Ins. tab.")

    # Insurance section
    ins = pane.child_window(auto_id="GroupBox2", control_type="Group")

    # Insurance Name — free-text combo
    try:
        ins.child_window(auto_id="cb1InsName", control_type="ComboBox") \
           .child_window(auto_id="1001", control_type="Edit") \
           .set_edit_text(payload.ins_name.upper())
        logger.info("Insurance name set.")
    except Exception:
        logger.error("Insurance Name field not found.")
        raise RuntimeError("Insurance Name field unavailable.")

    # Insurance Type — dropdown
    _set_combo(ins, "cb1InsType", payload.ins_type, "insurance type")

    # Address / contact fields
    _set_edit(ins, "txt1InsAdd1",   payload.ins_address,       "insurance address")
    _set_edit(ins, "txt1InsCity",   payload.ins_city,          "insurance city")
    _set_edit(ins, "txt1InsState",  payload.ins_state,         "insurance state")
    _set_edit(ins, "txt1InsZip",    payload.ins_zip,           "insurance zip")
    _set_edit(ins, "txt1InsPhone",  payload.ins_phone,         "insurance phone")

    # Policy / group numbers
    _set_edit(ins, "txt1InsPolicy", payload.ins_policy_number, "policy number")
    _set_edit(ins, "txt1InsGroup",  payload.ins_group_number,  "group number")

    logger.info("Primary Ins. tab filled.")


def _save_and_close(app: Application) -> None:
    """Click Save and Close on the Registration screen."""
    try:
        main_win = app.window(auto_id="frmMain")
        reg_win = main_win.child_window(auto_id="frmRegistration", control_type="Window")
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
    timings.Timings.fast()

    app = connect_to_epower()
    _click_patient_row(app, payload)
    _click_demographics(app)
    _fill_demographics(app, payload)
    _fill_guarantor(app, payload)
    _fill_employer_tab(app, payload)
    _fill_primary_ins_tab(app, payload)
    _save_and_close(app)

    logger.info("Input demographics flow completed.")
    return {"status": "success"}
