# passenv

**Manage multiple isolated [`pass(1)`](https://www.passwordstore.org/) password stores — from any shell.**

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Tests](https://img.shields.io/badge/tests-52%20passing-brightgreen.svg)

`pass` gives you one password store. `passenv` gives you as many as you want —
*work*, *personal*, *client-a*, *labs* — and lets you switch between them with a
single command while leaving your default `~/.password-store` completely
untouched.

It began as a pair of zsh functions (`passmanager` / `passenv`) and is now a
pip-installable Python CLI that works identically in **bash, zsh, fish**, or
any shell with Python available.

---

## Features

- **Multiple isolated stores** — each environment is a full, independent
  password store with its own GPG recipients and git history.
- **Zero impact on `pass`** — `passenv` only sets `PASSWORD_STORE_DIR` for its
  own invocations. Your default store and the bare `pass` command behave
  exactly as before.
- **Transparent pass-through** — anything `passenv` doesn't recognize as one
  of its own commands is forwarded verbatim to `pass`, including flags,
  exit codes, and interactive prompts:
  `passenv show Sites/github` ≡ `PASSWORD_STORE_DIR=... pass show Sites/github`.
- **Persistent selection** — the active environment lives in a file on disk,
  so it is shared across all shells, sessions, and terminals.
- **Two familiar interfaces** — the original flag-style `passmanager`
  *and* a modern subcommand interface (`passenv env …`).
- **Safe by default** — removing an environment requires typing `DELETE`;
  failed environment creation cleans up after itself.

---

## Requirements

- Python **3.10+**
- [`pass(1)`](https://www.passwordstore.org/) on `PATH`
- `gpg` (only needed when creating new environments)

## Installation

```bash
pip install passenv
```

Recommended, to keep the CLI isolated from your system Python:

```bash
pipx install passenv
```

From source:

```bash
git clone https://github.com/amirgard0/passenv.git
cd passenv
pip install .
```

This installs two commands:

| Command | Purpose |
|---------|---------|
| `passenv` | transparent `pass(1)` wrapper for the active environment |
| `passmanager` | environment management (original flag-style interface) |

---

## Quick start

```bash
# Create a new environment (lists your GPG keys, prompts for one)
passmanager --add work

# Switch to it
passmanager --go work

# Use pass exactly as you normally would — just prefix with passenv
passenv ls
passenv insert email/gmail.com
passenv generate -n 20 github.com
passenv show Sites/daytona.io
passenv -c github.com          # copy to clipboard

# See where you are
passmanager --show
passmanager --list
```

---

## Usage

### `passenv` — day-to-day password access

Everything after `passenv` is forwarded verbatim to `pass`, scoped to the
active environment:

```bash
passenv                        # show the password tree
passenv ls                     # list passwords
passenv show Sites/github.com  # show one password
passenv insert email/gmail     # insert a new password
passenv generate -n 20 github  # generate a password
passenv cp old new             # copy an entry
passenv git log                # even git commands work
```

Switching environments without leaving the `passenv` habit:

```bash
passenv -g work      # or: passenv --go work
```

### `passmanager` — environment management

```text
passmanager                        show usage
passmanager --list                 list all environments (* marks active)
passmanager --show                 show the active environment
passmanager --go <environment>     switch to an environment
passmanager -g <environment>       shortcut for --go
passmanager --add <environment>    create a new environment (prompts for GPG key)
passmanager --remove <environment> permanently delete an environment
```

`--add` first prints `gpg --list-secret-keys --keyid-format LONG`, then asks
which key to use. `--remove` asks you to type `DELETE` to confirm — any other
answer cancels.

### `passenv env` — the same thing, subcommand style

If you prefer one command, all management operations are also available as
subcommands:

```bash
passenv env list      # or: passenv env ls
passenv env show
passenv env go work   # or: passenv env g work
passenv env add work
passenv env remove work
```

---

## How it works

```
~/.passenvs/                 ← PASSENV_ROOT
├── .current                 ← name of the active environment (plain text)
├── work/                    ← a complete password store
│   └── .gpg-id
├── personal/
│   └── .gpg-id
└── randomaccounts/
    └── .gpg-id
```

Each environment directory is a full `PASSWORD_STORE_DIR`. When you run
`passenv <args>`, it:

1. Reads the active environment name from `$PASSENV_ROOT/.current`
2. Resolves it to `$PASSENV_ROOT/<environment>`
3. Executes `pass <args>` with `PASSWORD_STORE_DIR` pointing there

Nothing is injected into your shell, no aliases are required, and the bare
`pass` command always targets your default store.

### Configuration

| Variable       | Default      | Description                          |
|----------------|--------------|--------------------------------------|
| `PASSENV_ROOT` | `~/.passenvs`| Root directory for all environments  |

Example — keep environments on an encrypted volume:

```bash
export PASSENV_ROOT=/mnt/vault/passenvs
```

---

## Example session

```console
$ passmanager --add work
Creating pass environment: work

Available GPG keys:

sec   ed25519/966F948543F1A89E 2026-07-07 [SC]
      0B44CECAA4BE92FFBEA725DC966F948543F1A89E
uid                 [ultimate] you <you@example.com>

GPG key ID/email to use: you@example.com

Initializing pass environment...
Password store initialized for you@example.com

Environment 'work' created successfully.

$ passmanager --go work
Switched to pass environment: work
Directory: /home/you/.passenvs/work

$ passenv insert github.com
Enter password for github.com: ********
Retype password for github.com: ********

$ passenv ls
Password Store
└── github.com

$ passmanager --list
Pass environments:

  * work  (active)
```

---

## Migrating from the zsh script

If you previously used the shell-function version:

1. Delete the `passmanager` / `passenv` functions (and their `compdef` lines)
   from your `~/.oh-my-zsh/custom/` files.
2. Restart your shell.

Nothing else changes — both versions use the same `~/.passenvs` layout and
`.current` file, so all existing environments keep working.

> **Note:** zsh *functions* shadow same-named binaries in `$PATH`. Until the
> old functions are removed, typing `passenv` will still run the shell
> function.

---

## Development

```bash
git clone https://github.com/amirgard0/passenv.git
cd passenv

# install with dev dependencies
pip install -e ".[dev]"

# run the test suite
pytest

# build distributable packages
pip install build
python -m build
```

Project layout:

```
passenv/
├── passenv/
│   ├── cli.py       # two entry points + passthrough group
│   ├── core.py      # environment CRUD, typed errors
│   └── config.py    # paths, .current file I/O
├── tests/
│   └── test_passenv.py
├── pyproject.toml
├── LICENSE
└── README.md
```

---

## License

[MIT](LICENSE) © Amir Hossain Zare
