"""Native desktop launcher for Running Dashboard.

The web application remains unchanged: this module binds it to localhost,
stores user data outside the application bundle and opens it in a native
pywebview window.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import platform
import socket
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen


APP_NAME = "Running Dashboard"
SETTINGS_FILENAME = "desktop-settings.json"


def user_data_dir() -> Path:
    """Return the writable per-user directory for the current platform."""
    override = os.getenv("RUNNING_DESKTOP_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    system = platform.system()
    if system == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        root = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / APP_NAME


def load_desktop_settings(data_dir: Path) -> dict[str, str]:
    path = data_dir / SETTINGS_FILENAME
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def configure_environment(data_dir: Path) -> None:
    """Point the server at persistent storage before importing app.main."""
    data_dir.mkdir(parents=True, exist_ok=True)
    settings = load_desktop_settings(data_dir)
    os.environ["RUNNING_DATA_DIR"] = str(data_dir)
    os.environ["RUNNING_DESKTOP"] = "1"
    if not os.getenv("OPENAI_API_KEY") and settings.get("openai_api_key"):
        os.environ["OPENAI_API_KEY"] = str(settings["openai_api_key"]).strip()
    if not os.getenv("RUNNING_OPENAI_MODEL") and settings.get("openai_model"):
        os.environ["RUNNING_OPENAI_MODEL"] = str(settings["openai_model"]).strip()


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_until_ready(url: str, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{url}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            time.sleep(0.1)
    raise RuntimeError("Running Dashboard non si è avviata entro il tempo previsto")


def setup_logging(data_dir: Path) -> None:
    logging.basicConfig(
        filename=data_dir / "running-dashboard.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    # CI exercises the exact frozen pythonnet/CLR path used by pywebview on
    # Windows without opening a GUI. This catches broken bundles before they
    # are uploaded as release artifacts.
    if os.getenv("RUNNING_DESKTOP_SMOKE_TEST") == "1":
        if platform.system() == "Windows":
            import clr  # noqa: F401
        return 0

    data_dir = user_data_dir()
    configure_environment(data_dir)
    setup_logging(data_dir)

    # Import only after RUNNING_DATA_DIR has been configured.
    import uvicorn
    import webview
    from app.main import app
    from desktop.integration import attach_desktop

    attach_desktop(app)

    port = free_local_port()
    base_url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    )
    thread = threading.Thread(target=server.run, name="running-dashboard-server", daemon=True)
    thread.start()

    try:
        wait_until_ready(base_url)
        webview.create_window(
            APP_NAME,
            base_url,
            width=1360,
            height=900,
            min_size=(920, 650),
            text_select=True,
        )
        webview.start(debug=os.getenv("RUNNING_DESKTOP_DEBUG") == "1")
        return 0
    except Exception:
        logging.exception("Desktop launcher failed")
        raise
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
