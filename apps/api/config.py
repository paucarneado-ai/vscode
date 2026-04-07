from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "OpenClaw")
    app_env: str = os.getenv("APP_ENV", "development")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "info")
    api_key: str = os.getenv("OPENCLAW_API_KEY", "")
    # Rate limit for public intake endpoints (per IP)
    rate_limit_max: int = int(os.getenv("RATE_LIMIT_MAX", "10"))
    rate_limit_window_seconds: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))


settings = Settings()