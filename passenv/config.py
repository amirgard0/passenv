"""Configuration and path constants for passenv.

All paths respect the standard XDG Base Directory Specification where
applicable and can be overridden via environment variables.
"""

import os
from pathlib import Path


def _default_passenv_root() -> Path:
    """Return the default root directory for pass environments.

    Resolution order:
      1. ``PASSENV_ROOT`` environment variable
      2. ``~/.passenvs`` (legacy default, matches the shell script)
    """
    return Path(os.environ.get("PASSENV_ROOT", Path.home() / ".passenvs"))


PASSENV_ROOT: Path = _default_passenv_root()
"""Root directory that holds all pass environments."""

CURRENT_FILE: Path = PASSENV_ROOT / ".current"
"""File that stores the name of the currently active environment."""


def get_passenv_root() -> Path:
    """Return the passenv root directory (always re-reads env vars)."""
    return Path(os.environ.get("PASSENV_ROOT", Path.home() / ".passenvs"))


def get_current_file() -> Path:
    """Return the path to the ``.current`` marker file."""
    return get_passenv_root() / ".current"


def load_current_env() -> str | None:
    """Read the active environment name from disk.

    Returns ``None`` when no environment is selected or the file is absent.
    """
    path = get_current_file()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip() or None
    return None


def save_current_env(name: str | None) -> None:
    """Persist the active environment name to disk.

    Passing ``None`` removes the marker file entirely.
    """
    root = get_passenv_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".current"
    if name:
        path.write_text(f"{name}\n", encoding="utf-8")
    else:
        path.unlink(missing_ok=True)
