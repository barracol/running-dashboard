from dataclasses import dataclass
from contextvars import ContextVar, Token
from pathlib import Path
import os


_desktop_profile: ContextVar[str] = ContextVar("running_desktop_profile", default="user")


def set_desktop_profile(profile: str) -> Token:
    return _desktop_profile.set("demo" if profile == "demo" else "user")


def reset_desktop_profile(token: Token) -> None:
    _desktop_profile.reset(token)


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_path: Path
    upload_dir: Path
    openai_api_key: str
    openai_model: str
    ai_gateway_url: str
    ai_gateway_token: str


def get_settings() -> Settings:
    data_dir = Path(os.getenv("RUNNING_DATA_DIR", "data")).resolve()
    if os.getenv("RUNNING_DESKTOP") == "1":
        data_dir = data_dir / "profiles" / _desktop_profile.get()
    database_path = Path(os.getenv("RUNNING_DB_PATH", data_dir / "running.db")).resolve()
    upload_dir = Path(os.getenv("RUNNING_UPLOAD_DIR", data_dir / "uploads")).resolve()
    return Settings(
        data_dir=data_dir,
        database_path=database_path,
        upload_dir=upload_dir,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("RUNNING_OPENAI_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini",
        ai_gateway_url=os.getenv("AI_GATEWAY_URL", "").strip().rstrip("/"),
        ai_gateway_token=os.getenv("INTERNAL_CALENDAR_TOKEN", "").strip(),
    )
