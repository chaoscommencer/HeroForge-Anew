"""Remove risky keys from persisted Claude Code user settings.

Usage (from persist-claude-state.sh, on the system Python in isolated mode)::

    /usr/bin/python3 -I -S -B clean_settings.py QUARANTINE SETTINGS [SETTINGS ...]

``settings.json`` and ``settings.local.json`` live on the Codespace's persistent
disk and are linked back into ``~/.claude`` at every start, so a key that any
process running as the user writes there survives "Rebuild Container". The keys
below either run a command (hooks, the status line, credential helpers), widen
what Claude Code may do without asking (permission grants, MCP servers), or
change how its commands and traffic resolve (risky ``env`` entries). Each one
found is removed, the file is rewritten without it, the original is kept in
QUARANTINE, and a line names what was removed. Hooks and similar settings you
want belong in the project's ``.claude/settings.json``, which git reviews.

A SETTINGS path that is absent is passed over. One that is a link, no regular
file, larger than MAX_BYTES, or not a JSON object is left as it is, with a line
saying so: Claude Code rejects a file it cannot parse, so such a file runs
nothing. The exit status is 1 when a file holding a risky key could not be
cleaned, 0 otherwise.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
from pathlib import Path
from typing import Any

PREFIX = "persist-claude-state:"

# A settings file larger than this is not one Claude Code wrote.
MAX_BYTES = 1 << 20

# Top-level keys whose value runs a command or switches on code from elsewhere.
RISKY_KEYS = frozenset(
    {
        "hooks",
        "statusLine",
        "fileSuggestion",
        "apiKeyHelper",
        "awsCredentialExport",
        "awsAuthRefresh",
        "otelHeadersHelper",
        "enableAllProjectMcpServers",
        "enabledMcpjsonServers",
    }
)

# Keys under "permissions" that grant more than the default asks for.
RISKY_PERMISSION_KEYS = frozenset({"allow", "additionalDirectories"})

# A "permissions.defaultMode" that skips every prompt.
RISKY_DEFAULT_MODES = frozenset({"bypassPermissions"})

# "env" names (compared upper-cased) that change which programs or libraries
# run, where Claude Code's traffic goes, or which certificates it trusts.
RISKY_ENV_NAMES = frozenset(
    {
        "PATH",
        "SHELL",
        "BASH_ENV",
        "ENV",
        "CLAUDE_CODE_SHELL",
        "CLAUDE_CODE_SHELL_PREFIX",
        "NODE_OPTIONS",
        "NODE_PATH",
        "NODE_EXTRA_CA_CERTS",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONHOME",
        "PERL5LIB",
        "PERL5OPT",
        "RUBYOPT",
        "EDITOR",
        "VISUAL",
        "BROWSER",
        "PAGER",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
    }
)

# "env" name prefixes (upper-cased) of the same kind: the dynamic loader and git.
RISKY_ENV_PREFIXES = ("LD_", "GIT_")


def is_risky_env(name: str) -> bool:
    upper = name.upper()
    return upper in RISKY_ENV_NAMES or upper.startswith(RISKY_ENV_PREFIXES)


def strip(settings: dict[str, Any]) -> list[str]:
    """Remove every risky key from *settings* in place; the removed keys' names."""
    removed: list[str] = []
    for key in sorted(RISKY_KEYS & settings.keys()):
        del settings[key]
        removed.append(key)
    permissions = settings.get("permissions")
    if isinstance(permissions, dict):
        for key in sorted(RISKY_PERMISSION_KEYS & permissions.keys()):
            del permissions[key]
            removed.append(f"permissions.{key}")
        if permissions.get("defaultMode") in RISKY_DEFAULT_MODES:
            del permissions["defaultMode"]
            removed.append("permissions.defaultMode")
    env = settings.get("env")
    if isinstance(env, dict):
        for name in sorted(key for key in env if is_risky_env(str(key))):
            del env[name]
            removed.append(f"env.{name}")
    return removed


def read_regular(path: Path) -> bytes | None:
    """The bytes of the regular file at *path*, read through no link; None otherwise.

    Raises FileNotFoundError when it is absent.
    """
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        )
    except FileNotFoundError:
        raise
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        raw = os.read(descriptor, MAX_BYTES + 1)
    finally:
        os.close(descriptor)
    return raw if len(raw) <= MAX_BYTES else None


def write_new(path: Path, content: bytes) -> None:
    """*content* in a new, owner-only file at *path*; fails if anything is there."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, content)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def quarantine_directory(quarantine: Path) -> Path:
    """*quarantine*, made owner-only when missing; refused when it is a link or
    anything but a directory of this user's own."""
    try:
        quarantine.mkdir(mode=0o700)
    except FileExistsError:
        pass
    found = os.lstat(quarantine)
    if not stat.S_ISDIR(found.st_mode) or found.st_uid != os.geteuid():
        raise OSError(f"{quarantine} is not a directory of this user's own")
    return quarantine


def clean(quarantine: Path, path: Path) -> bool:
    """*path* without its risky keys; False when one was found and not removed."""
    try:
        raw = read_regular(path)
    except FileNotFoundError:
        return True
    if raw is None:
        sys.stderr.write(
            f"{PREFIX} {path} is no regular file of a settings file's size; left as is."
            + "\n"
        )
        return True
    try:
        settings = json.loads(raw)
    except ValueError:
        sys.stderr.write(f"{PREFIX} {path} is not valid JSON; left as is." + "\n")
        return True
    if not isinstance(settings, dict):
        sys.stderr.write(f"{PREFIX} {path} holds no JSON object; left as is." + "\n")
        return True
    removed = strip(settings)
    if not removed:
        return True
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    temporary = path.with_name(f".{path.name}.{os.getpid()}.cleaning")
    try:
        kept = quarantine_directory(quarantine) / f"{path.name}.{stamp}.{os.getpid()}"
        write_new(kept, raw)
        cleaned = (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode()
        write_new(temporary, cleaned)
        # Replaces the name, never writing through a link swapped in there.
        os.replace(temporary, path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        sys.stderr.write(
            f"{PREFIX} {path} holds {', '.join(removed)}, which could not be removed "
            f"({error}); it is left out.\n"
        )
        return False
    sys.stderr.write(
        f"{PREFIX} removed {', '.join(removed)} from {path}, which runs commands or "
        f"widens permissions across rebuilds; the original is kept as {kept}. Put "
        "settings like these in the project's .claude/settings.json instead.\n"
    )
    return True


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write(f"{PREFIX} clean_settings.py: QUARANTINE SETTINGS...\n")
        return 2
    quarantine = Path(argv[1])
    results = [clean(quarantine, Path(path)) for path in argv[2:]]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
