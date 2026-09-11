import os
import subprocess
import sys
from pathlib import Path

import pytest

from passenv import __version__
from passenv.config import get_passenv_root, get_current_file, load_current_env, save_current_env
from passenv.core import (
    EnvironmentNotFoundError,
    env_dir,
    get_current,
    list_environments,
    remove_environment,
    set_current,
    validate_env_exists,
)


@pytest.fixture
def tmp_passenv_root(monkeypatch, tmp_path):
    monkeypatch.setenv("PASSENV_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def empty_env(tmp_passenv_root):
    set_current(None)
    assert get_current() is None
    return tmp_passenv_root


def test_version():
    assert isinstance(__version__, str)
    assert len(__version__.split(".")) >= 2


def test_load_current_env_no_file(empty_env):
    assert load_current_env() is None


def test_save_and_load_current_env(empty_env):
    save_current_env("myenv")
    assert load_current_env() == "myenv"
    assert get_current_file().is_file()


def test_save_none_removes_file(empty_env):
    save_current_env("myenv")
    assert get_current_file().is_file()
    save_current_env(None)
    assert not get_current_file().is_file()


def test_env_dir_returns_path(empty_env):
    assert env_dir("testenv") == get_passenv_root() / "testenv"


def test_list_environments_empty(empty_env):
    assert list_environments() == []


def test_list_environments_with_dirs(empty_env):
    root = get_passenv_root()
    for name in ["env1", "env2", "env3"]:
        (root / name).mkdir()
    (root / ".hidden").mkdir()
    (root / "readme.txt").write_text("hello")
    assert list_environments() == ["env1", "env2", "env3"]


def test_get_current_none_when_unset(empty_env):
    assert get_current() is None


def test_set_current_writes_to_disk(empty_env):
    set_current("dev")
    assert get_current() == "dev"


def test_set_current_none_clears(empty_env):
    set_current("dev")
    set_current(None)
    assert get_current() is None


def test_validate_env_exists_missing(empty_env):
    with pytest.raises(EnvironmentNotFoundError):
        validate_env_exists("nonexistent")


def test_validate_env_exists_ok(empty_env):
    d = get_passenv_root() / "myenv"
    d.mkdir()
    assert validate_env_exists("myenv") == d


def test_remove_environment_missing(empty_env):
    with pytest.raises(EnvironmentNotFoundError):
        remove_environment("ghost")


def test_remove_environment_deletes_dir(empty_env):
    (get_passenv_root() / "oldenv").mkdir()
    remove_environment("oldenv")
    assert not (get_passenv_root() / "oldenv").is_dir()


def test_remove_environment_clears_current(empty_env):
    (get_passenv_root() / "toberemoved").mkdir()
    set_current("toberemoved")
    remove_environment("toberemoved")
    assert get_current() is None


def test_remove_environment_preserves_other_current(empty_env):
    root = get_passenv_root()
    (root / "keep").mkdir()
    (root / "remove").mkdir()
    set_current("keep")
    remove_environment("remove")
    assert get_current() == "keep"


from click.testing import CliRunner
from passenv.cli import cli, passmanager


class FakeProc:
    returncode = 0
    stdout = ""
    stderr = ""


def _invoke_passenv(args, input=None):
    return CliRunner().invoke(cli, args, input=input)


def _invoke_pm(args, input=None):
    return CliRunner().invoke(passmanager, args, input=input)


def _fake_run_pass(monkeypatch):
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append((list(cmd), kwargs.get("env", {})))
        return FakeProc()
    monkeypatch.setattr("passenv.cli.subprocess.run", fake_run)
    monkeypatch.setattr("passenv.cli.shutil.which", lambda name: f"/usr/bin/{name}")
    return calls


def test_cli_forwards_to_pass(empty_env, monkeypatch):
    calls = _fake_run_pass(monkeypatch)
    (get_passenv_root() / "myenv").mkdir()
    set_current("myenv")

    r = _invoke_passenv(["show", "Sites/daytona.io"])
    assert r.exit_code == 0
    assert calls[0][0] == ["pass", "show", "Sites/daytona.io"]
    assert calls[0][1]["PASSWORD_STORE_DIR"].endswith("myenv")


def test_cli_no_args_forwards_to_pass(empty_env, monkeypatch):
    calls = _fake_run_pass(monkeypatch)
    (get_passenv_root() / "myenv").mkdir()
    set_current("myenv")

    r = _invoke_passenv([])
    assert r.exit_code == 0
    assert calls[0][0] == ["pass"]


def test_cli_passthrough_flags(empty_env, monkeypatch):
    calls = _fake_run_pass(monkeypatch)
    (get_passenv_root() / "myenv").mkdir()
    set_current("myenv")

    r = _invoke_passenv(["-c", "entry"])
    assert r.exit_code == 0
    assert calls[0][0] == ["pass", "-c", "entry"]


def test_cli_no_env_selected(empty_env):
    r = _invoke_passenv(["ls"])
    assert r.exit_code == 1
    assert "no pass environment selected" in r.output


def test_cli_g_shortcut(empty_env):
    (get_passenv_root() / "work").mkdir()
    r = _invoke_passenv(["-g", "work"])
    assert r.exit_code == 0
    assert "Switched to pass environment: work" in r.output
    assert get_current() == "work"


def test_cli_g_shortcut_nonexistent(empty_env):
    r = _invoke_passenv(["-g", "ghost"])
    assert r.exit_code == 1
    assert "does not exist" in r.output


def test_cli_go_long_option(empty_env):
    (get_passenv_root() / "work").mkdir()
    r = _invoke_passenv(["--go", "work"])
    assert r.exit_code == 0
    assert get_current() == "work"


def test_cli_env_list(empty_env):
    (get_passenv_root() / "alpha").mkdir()
    set_current("alpha")
    r = _invoke_passenv(["env", "list"])
    assert r.exit_code == 0
    assert "Pass environments:" in r.output
    assert "* alpha" in r.output


def test_cli_env_ls_alias(empty_env):
    (get_passenv_root() / "alpha").mkdir()
    r = _invoke_passenv(["env", "ls"])
    assert r.exit_code == 0
    assert "alpha" in r.output


def test_cli_env_show(empty_env):
    (get_passenv_root() / "alpha").mkdir()
    set_current("alpha")
    r = _invoke_passenv(["env", "show"])
    assert r.exit_code == 0
    assert "Current environment: alpha" in r.output


def test_cli_env_show_no_selection(empty_env):
    r = _invoke_passenv(["env", "show"])
    assert r.exit_code == 0
    assert "No pass environment selected." in r.output


def test_cli_env_go(empty_env):
    (get_passenv_root() / "work").mkdir()
    r = _invoke_passenv(["env", "go", "work"])
    assert r.exit_code == 0
    assert get_current() == "work"


def test_cli_env_go_nonexistent(empty_env):
    r = _invoke_passenv(["env", "go", "ghost"])
    assert r.exit_code == 1
    assert "does not exist" in r.output


def test_cli_env_add(empty_env, monkeypatch):
    calls = _fake_run_pass(monkeypatch)
    r = _invoke_passenv(["env", "add", "newenv", "--gpg-key", "ABC123"])
    assert r.exit_code == 0
    assert "created successfully" in r.output
    assert (get_passenv_root() / "newenv").is_dir()
    assert calls[-1][0] == ["pass", "init", "ABC123"]


def test_cli_env_add_already_exists(empty_env):
    (get_passenv_root() / "dup").mkdir()
    r = _invoke_passenv(["env", "add", "dup", "--gpg-key", "ABC"])
    assert r.exit_code == 1
    assert "already exists" in r.output


def test_cli_env_add_init_fails_cleans_up(empty_env, monkeypatch):
    def fake_run(cmd, **kwargs):
        p = FakeProc()
        if "init" in cmd:
            p.returncode = 1
        return p
    monkeypatch.setattr("passenv.cli.subprocess.run", fake_run)

    r = _invoke_passenv(["env", "add", "failenv", "--gpg-key", "ABC"])
    assert r.exit_code == 1
    assert not (get_passenv_root() / "failenv").exists()


def test_cli_env_remove_confirmed(empty_env):
    (get_passenv_root() / "killme").mkdir()
    r = _invoke_passenv(["env", "remove", "killme"], input="DELETE\n")
    assert r.exit_code == 0
    assert not (get_passenv_root() / "killme").exists()


def test_cli_env_remove_cancelled(empty_env):
    (get_passenv_root() / "spare").mkdir()
    r = _invoke_passenv(["env", "remove", "spare"], input="nope\n")
    assert r.exit_code == 1
    assert "Cancelled." in r.output
    assert (get_passenv_root() / "spare").is_dir()


def test_cli_env_remove_clears_current(empty_env):
    (get_passenv_root() / "active").mkdir()
    set_current("active")
    r = _invoke_passenv(["env", "remove", "active"], input="DELETE\n")
    assert r.exit_code == 0
    assert get_current() is None


def test_cli_help():
    r = _invoke_passenv(["--help"])
    assert r.exit_code == 0
    assert "env" in r.output


def test_cli_env_help():
    r = _invoke_passenv(["env", "--help"])
    assert r.exit_code == 0


def test_pm_usage_when_no_flags():
    r = _invoke_pm([])
    assert r.exit_code == 0
    assert "Usage:" in r.output
    assert "--list" in r.output
    assert "--go" in r.output


def test_pm_list(empty_env):
    (get_passenv_root() / "alpha").mkdir()
    set_current("alpha")
    r = _invoke_pm(["--list"])
    assert r.exit_code == 0
    assert "Pass environments:" in r.output
    assert "* alpha" in r.output


def test_pm_show(empty_env):
    (get_passenv_root() / "alpha").mkdir()
    set_current("alpha")
    r = _invoke_pm(["--show"])
    assert r.exit_code == 0
    assert "Current environment: alpha" in r.output


def test_pm_show_no_selection(empty_env):
    r = _invoke_pm(["--show"])
    assert r.exit_code == 0
    assert "No pass environment selected." in r.output


def test_pm_go(empty_env):
    (get_passenv_root() / "work").mkdir()
    r = _invoke_pm(["--go", "work"])
    assert r.exit_code == 0
    assert "Switched to pass environment: work" in r.output
    assert get_current() == "work"


def test_pm_g_shortcut(empty_env):
    (get_passenv_root() / "work").mkdir()
    r = _invoke_pm(["-g", "work"])
    assert r.exit_code == 0
    assert get_current() == "work"


def test_pm_go_nonexistent(empty_env):
    r = _invoke_pm(["--go", "ghost"])
    assert r.exit_code == 1
    assert "does not exist" in r.output


def test_pm_add(empty_env, monkeypatch):
    calls = _fake_run_pass(monkeypatch)
    r = _invoke_pm(["--add", "newenv"], input="ABC123\n")
    assert r.exit_code == 0
    assert "created successfully" in r.output
    assert (get_passenv_root() / "newenv").is_dir()
    assert calls[-1][0] == ["pass", "init", "ABC123"]


def test_pm_add_no_key_aborts(empty_env, monkeypatch):
    monkeypatch.setattr("passenv.cli.subprocess.run", lambda cmd, **kw: FakeProc())
    r = _invoke_pm(["--add", "nokey"], input="\n")
    assert r.exit_code == 1
    assert "no GPG key" in r.output
    assert not (get_passenv_root() / "nokey").exists()


def test_pm_add_already_exists(empty_env):
    (get_passenv_root() / "dup").mkdir()
    r = _invoke_pm(["--add", "dup"], input="ABC\n")
    assert r.exit_code == 1
    assert "already exists" in r.output


def test_pm_remove_confirmed(empty_env):
    (get_passenv_root() / "killme").mkdir()
    r = _invoke_pm(["--remove", "killme"], input="DELETE\n")
    assert r.exit_code == 0
    assert not (get_passenv_root() / "killme").exists()


def test_pm_remove_cancelled(empty_env):
    (get_passenv_root() / "spare").mkdir()
    r = _invoke_pm(["--remove", "spare"], input="no\n")
    assert r.exit_code == 1
    assert "Cancelled." in r.output
    assert (get_passenv_root() / "spare").is_dir()


def test_pm_remove_nonexistent(empty_env):
    r = _invoke_pm(["--remove", "ghost"], input="DELETE\n")
    assert r.exit_code == 1
    assert "does not exist" in r.output


PROJECT_ROOT = Path(__file__).parents[1]


def _run_cli_subprocess(args, input=None):
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "passenv", *args],
        capture_output=True, text=True, env=env, cwd=str(PROJECT_ROOT), input=input,
    )


def test_subprocess_help():
    r = _run_cli_subprocess(["--help"])
    assert r.returncode == 0
    assert "env" in r.stdout


def test_subprocess_passthrough_no_env(tmp_passenv_root):
    r = _run_cli_subprocess(["ls"])
    assert r.returncode == 1
    assert "no pass environment selected" in (r.stdout + r.stderr).lower()
