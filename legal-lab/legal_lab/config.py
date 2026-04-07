from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "LegalLab")
    app_env: str = os.getenv("APP_ENV", "development")
    app_port: int = int(os.getenv("APP_PORT", "8100"))
    log_level: str = os.getenv("LOG_LEVEL", "info")
    api_key: str = os.getenv("LEGAL_LAB_API_KEY", "")


settings = Settings()
