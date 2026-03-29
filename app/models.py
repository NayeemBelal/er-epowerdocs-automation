from pydantic import BaseModel, ConfigDict, field_validator
import re


class PatientPayload(BaseModel):
    """
    Inbound PHI payload from the webhook.

    HIPAA note: This model exists only in volatile RAM during request
    processing. It must never be serialized to disk, included in log
    output, or persisted in any form.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str
    last_name: str
    dob: str            # Expected format: YYYY-MM-DD
    gender: str         # "M" or "F"
    cell_number: str
    chief_complaint: str
    insurance_id: str

    @field_validator("dob")
    @classmethod
    def validate_dob_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("dob must be in YYYY-MM-DD format")
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        v = v.upper()
        if v not in ("M", "F"):
            raise ValueError("gender must be 'M' or 'F'")
        return v
