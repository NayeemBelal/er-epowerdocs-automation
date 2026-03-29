from pydantic import BaseModel, ConfigDict


class InputDemographicsPayload(BaseModel):
    """
    Inbound PHI payload for the input demographics flow.

    HIPAA: exists only in volatile RAM during request processing.
    Must never be serialized to disk, logged, or persisted.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str
    last_name: str
