"""Command-line interface for passenv.

Two entry points, mirroring the original zsh functions exactly:

- ``passenv``     — transparent wrapper around ``pass(1)``: any unknown
  arguments are forwarded to ``pass`` with ``PASSWORD_STORE_DIR`` pointed at
  the active environment.  Environment management lives under the ``env``
  subcommand group.
- ``passmanager`` — the original flag-style interface (``--list``, ``--show``,
  ``--go``/``-g``, ``--add``, ``--remove``).
"""

import os
import shutil
import subprocess

import click

from passenv.config import get_current_file
from passenv.core import (
    ensure_passenv_root,
    env_dir,
    get_current,
    list_environments,
    remove_environment,
    set_current,
    validate_env_exists,
)


def _run_pass(pass_args: list[str]) -> None:
    current = get_current()
    if not current:
        click.echo("Error: no pass environment selected.")
        click.echo()
        click.echo("Select one with:")
        click.echo("  passmanager --go <environment>")
        raise SystemExit(1)

    d = env_dir(current)
    if not d.is_dir():
        click.echo("Error: current environment no longer exists:")
        click.echo(f"  {current}")
        get_current_file().unlink(missing_ok=True)
        set_current(None)
        raise SystemExit(1)

    if shutil.which("pass") is None:
        click.echo("Error: 'pass' binary not found on PATH.")
        raise SystemExit(1)

    env = os.environ.copy()
    env["PASSWORD_STORE_DIR"] = str(d)

    proc = subprocess.run(["pass", *pass_args], env=env)
    raise SystemExit(proc.returncode)


def _print_env_list() -> None:
    current = get_current()
    click.echo("Pass environments:")
    click.echo()
    found = False
    for name in list_environments():
        found = True
        if name == current:
            click.echo(f"  * {name}  (active)")
        else:
            click.echo(f"    {name}")
    if not found:
        click.echo("  No environments created.")


def _execute_go(ctx: click.Context, name: str) -> None:
    d = env_dir(name)
    if not d.is_dir():
        click.echo(f"Error: environment '{name}' does not exist.")
        click.echo()
        _print_env_list()
        ctx.exit(1)

    set_current(name)
    click.echo(f"Switched to pass environment: {name}")
    click.echo(f"Directory: {d}")


def _show_current() -> None:
    current = get_current()
    if not current:
        click.echo("No pass environment selected.")
        return

    d = env_dir(current)
    if not d.is_dir():
        click.echo("Current environment no longer exists:")
        click.echo(f"  {current}")
        get_current_file().unlink(missing_ok=True)
        set_current(None)
        raise SystemExit(1)

    click.echo(f"Current environment: {current}")
    click.echo(f"Directory: {d}")


def _create_environment(name: str, gpg_key: str | None) -> None:
    target = env_dir(name)
    if target.exists():
        click.echo(f"Error: environment '{name}' already exists.")
        raise SystemExit(1)

    click.echo(f"Creating pass environment: {name}")
    click.echo()

    target.mkdir(parents=True, exist_ok=True)

    if gpg_key is None:
        click.echo("Available GPG keys:")
        click.echo()
        try:
            subprocess.run(
                ["gpg", "--list-secret-keys", "--keyid-format", "LONG"],
                check=False,
            )
        except FileNotFoundError:
            click.echo("Warning: gpg not found on PATH.")
        click.echo()
        gpg_key = click.prompt("GPG key ID/email to use", default="").strip()
        if not gpg_key:
            click.echo("Error: no GPG key specified.")
            shutil.rmtree(target, ignore_errors=True)
            raise SystemExit(1)

    click.echo()
    click.echo("Initializing pass environment...")

    env = os.environ.copy()
    env["PASSWORD_STORE_DIR"] = str(target)
    result = subprocess.run(["pass", "init", gpg_key], env=env)
    if result.returncode != 0:
        click.echo("Error: failed to initialize environment.")
        shutil.rmtree(target, ignore_errors=True)
        raise SystemExit(1)

    click.echo()
    click.echo(f"Environment '{name}' created successfully.")
    click.echo()
    click.echo("Use:")
    click.echo(f"  passmanager --go {name}")


def _remove_environment_interactive(name: str) -> None:
    try:
        validate_env_exists(name)
    except Exception:
        click.echo(f"Error: environment '{name}' does not exist.")
        raise SystemExit(1)

    click.echo("WARNING: This will permanently delete:")
    click.echo(f"  {env_dir(name)}")
    click.echo()

    confirm = click.prompt("Type 'DELETE' to confirm", default="")

    if confirm != "DELETE":
        click.echo("Cancelled.")
        raise SystemExit(1)

    remove_environment(name)
    click.echo(f"Environment '{name}' removed.")


def _passthrough_callback(pass_args: tuple[str, ...]) -> None:
    _run_pass(list(pass_args))


_passthrough_command = click.Command(
    "pass",
    callback=_passthrough_callback,
    params=[click.Argument(["pass_args"], nargs=-1, type=click.UNPROCESSED)],
    context_settings={"ignore_unknown_options": True, "allow_interspersed_args": True},
)


class PassenvGroup(click.Group):
    """Group that forwards any unknown command straight to ``pass(1)``."""

    def resolve_command(self, ctx: click.Context, args: list[str]):
        if self.get_command(ctx, args[0]) is not None:
            return super().resolve_command(ctx, args)
        return "pass", _passthrough_command, list(args)


@click.group(cls=PassenvGroup, invoke_without_command=True, context_settings={"ignore_unknown_options": True})
@click.option("-g", "--go", "go_env", metavar="ENV", default=None,
              help="Switch to an environment (shortcut for 'passenv env go ENV').")
@click.pass_context
def cli(ctx: click.Context, go_env: str | None) -> None:
    """Pass Environment Manager.

    Any arguments that are not a subcommand are forwarded directly to
    pass(1) with PASSWORD_STORE_DIR set to the active environment.

    \b
    Examples:
      passenv                  show the password tree
      passenv ls               list passwords
      passenv show Sites/github show one password
      passenv -g work           switch to the 'work' environment
      passenv env list          list environments
      passenv env go work       switch environments
    """
    ensure_passenv_root()

    if go_env:
        _execute_go(ctx, go_env)
        return

    if ctx.invoked_subcommand is not None:
        return

    _run_pass([])


@click.group()
def env() -> None:
    """Manage pass environments."""


@env.command("list")
@click.option("-q", "--quiet", is_flag=True, help="Print environment names only.")
def env_list(quiet: bool) -> None:
    """List all pass environments."""
    if quiet:
        for name in list_environments():
            click.echo(name)
        return
    _print_env_list()


@env.command("show")
def env_show() -> None:
    """Show the currently active environment."""
    _show_current()


@env.command("go")
@click.argument("name")
@click.pass_context
def env_go(ctx: click.Context, name: str) -> None:
    """Switch to a pass environment."""
    _execute_go(ctx, name)


@env.command("add")
@click.argument("name")
@click.option("--gpg-key", "-k", default=None,
              help="GPG key ID/email to use (prompted interactively if omitted).")
def env_add(name: str, gpg_key: str | None) -> None:
    """Create a new pass environment."""
    _create_environment(name, gpg_key)


@env.command("remove")
@click.argument("name")
def env_remove(name: str) -> None:
    """Permanently remove a pass environment."""
    _remove_environment_interactive(name)


cli.add_command(env)
env.commands["ls"] = env.commands["list"]
env.commands["g"] = env.commands["go"]


_USAGE = """Usage:

  passmanager --list
  passmanager --show
  passmanager --go <environment>
  passmanager -g <environment>
  passmanager --add <environment>
  passmanager --remove <environment>"""


@click.command("passmanager", add_help_option=False, context_settings={"ignore_unknown_options": True})
@click.option("--list", "list_flag", is_flag=True, help="List all environments.")
@click.option("--show", "show_flag", is_flag=True, help="Show the current environment.")
@click.option("--go", "-g", "go_env", metavar="ENV", default=None, help="Switch to an environment.")
@click.option("--add", "add_env", metavar="ENV", default=None, help="Create a new environment.")
@click.option("--remove", "remove_env", metavar="ENV", default=None, help="Remove an environment.")
@click.argument("extra_args", nargs=-1, type=click.UNPROCESSED)
def passmanager(list_flag: bool, show_flag: bool, go_env: str | None,
                add_env: str | None, remove_env: str | None,
                extra_args: tuple[str, ...]) -> None:
    """Pass Environment Manager (original flag-style interface)."""
    if list_flag:
        _print_env_list()
        return

    if show_flag:
        _show_current()
        return

    if go_env is not None:
        _execute_go(click.get_current_context(), go_env)
        return

    if add_env is not None:
        _create_environment(add_env, None)
        return

    if remove_env is not None:
        _remove_environment_interactive(remove_env)
        return

    click.echo(_USAGE)
