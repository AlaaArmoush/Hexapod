import json
import os
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR_ENV = "HEXAPOD_DATA_DIR"


def data_dir() -> Path:
    configured = os.environ.get(DATA_DIR_ENV)
    if configured:
        return Path(configured).expanduser()
    return PROJECT_ROOT / "data"


def data_path(filename: str) -> Path:
    return data_dir() / filename


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def read_json_object(path: Path) -> Dict[str, Any]:
    value = read_json(path, {})
    if isinstance(value, dict):
        return value
    return {}
