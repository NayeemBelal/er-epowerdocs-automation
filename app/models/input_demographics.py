from typing import Optional

from pydantic import BaseModel, ConfigDict


class InputDemographicsPayload(BaseModel):
    """
    Inbound PHI payload for the input demographics flow.

    HIPAA: exists only in volatile RAM during request processing.
    Must never be serialized to disk, logged, or persisted.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    # Patient lookup
    first_name: str
    last_name: str

    # Address (three separate fields + street line)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None

    # Contact
    email: Optional[str] = None

    # Identity — all have EPD-safe defaults
    ssn: str = "000000000"
    marital_status: str = "Unknown"
    employer_name: Optional[str] = None  # non-null → sets status to Employed + fills Employer tab
    religion: str = "Unknown"
    race: str = "Declined to Specify"
    ethnicity: str = "Declined to Specify"
    preferred_language: str = "English"

    # Optional — no EPD default; omit from payload to leave unset
    how_did_you_hear: Optional[str] = None

    # Guarantor — omit both for adults (Same as Patient); provide both for minors
    guardian_first_name: Optional[str] = None
    guardian_last_name: Optional[str] = None

    # Primary insurance — omit ins_name to skip the Primary Ins. tab entirely
    ins_name: Optional[str] = None
    ins_type: Optional[str] = None
    ins_address: Optional[str] = None
    ins_city: Optional[str] = None
    ins_state: Optional[str] = None
    ins_zip: Optional[str] = None
    ins_phone: Optional[str] = None
    ins_policy_number: Optional[str] = None
    ins_group_number: Optional[str] = None
