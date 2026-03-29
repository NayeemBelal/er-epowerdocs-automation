from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    server_host: str = "127.0.0.1"
    server_port: int = 8000

    webhook_secret: str  # required — no default

    epower_process_name: str = "EPOWERdoc.exe"
    ui_timeout: int = 10  # seconds pywinauto waits for controls


settings = Settings()
