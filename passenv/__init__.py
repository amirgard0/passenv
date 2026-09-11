"""Pass Environment Manager — manage multiple pass(1) environments."""

__version__ = "0.1.0"

from passenv.core import (
    ensure_passenv_root,
    env_dir,
    get_current,
    list_environments,
    remove_environment,
    set_current,
)

__all__ = [
    "ensure_passenv_root",
    "env_dir",
    "get_current",
    "list_environments",
    "remove_environment",
    "set_current",
    "__version__",
]
