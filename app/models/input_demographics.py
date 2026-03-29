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
    employment_status: str = "Unknown"
    religion: str = "Unknown"
    race: str = "Declined to Specify"
    ethnicity: str = "Declined to Specify"
    preferred_language: str = "English"

    # Optional — no EPD default; omit from payload to leave unset
    how_did_you_hear: Optional[str] = None

    # Guarantor — omit both for adults (Same as Patient); provide both for minors
    guardian_first_name: Optional[str] = None
    guardian_last_name: Optional[str] = None
