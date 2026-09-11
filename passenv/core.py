"""Core logic for managing pass environments.

Every function returns plain values or raises typed exceptions so the CLI
layer stays a thin wrapper.
"""

import shutil
from pathlib import Path

from passenv.config import get_passenv_root, load_current_env, save_current_env


class EnvironmentNotFoundError(Exception):
    """Raised when an operation targets an environment that does not exist."""


def ensure_passenv_root() -> Path:
    """Create the passenv root directory if it does not exist."""
    root = get_passenv_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def env_dir(name: str) -> Path:
    """Return the directory path for a named environment."""
    return get_passenv_root() / name


def get_current() -> str | None:
    """Return the name of the currently active environment, or None."""
    return load_current_env()


def set_current(name: str | None) -> None:
    """Set the current environment by name.

    Passing ``None`` clears the selection.
    """
    save_current_env(name)


def list_environments() -> list[str]:
    """Return a sorted list of all environment directory names."""
    root = get_passenv_root()
    if not root.is_dir():
        return []
    return sorted(
        p.name for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def validate_env_exists(name: str) -> Path:
    """Verify that an environment exists; return its directory.

    Raises :class:`EnvironmentNotFoundError` if it does not.
    """
    d = env_dir(name)
    if not d.is_dir():
        raise EnvironmentNotFoundError(f"Environment '{name}' does not exist.")
    return d


def remove_environment(name: str) -> None:
    """Permanently delete an environment directory.

    If it was the active environment, the selection is cleared first.
    Raises :class:`EnvironmentNotFoundError` if the directory does not exist.
    """
    d = validate_env_exists(name)

    current = get_current()
    if name == current:
        set_current(None)

    shutil.rmtree(d)
