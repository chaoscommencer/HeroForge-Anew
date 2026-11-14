"""Set persist-claude-state's entries to owner-only modes through no link.

Usage (from persist-claude-state.sh, on the system Python in isolated mode)::

    /usr/bin/python3 -I -S -B narrow.py PERSIST CLAUDE_HOME KIND PATH [KIND PATH ...]

Each PATH, a KIND ("file" or "directory"), is set to 0600 (file) or 0700
(directory). No mode is changed through a link: a PATH that is a link is
resolved once, and what it leads to is opened as a path only
(``O_PATH | O_NOFOLLOW``), so no link is followed past that. It is changed only
when that descriptor is a KIND and, reached through a link, this user's own,
through the name the kernel gives it (``/proc/self/fd/N``).

What a link leads to is narrowed only inside PERSIST or CLAUDE_HOME (the
"roots"), checked on the path the link resolves to and again on what the kernel
opened there, so a parent directory swapped for a link in between narrows
nothing. A link elsewhere, to ``~/.bashrc`` say, is named and left as it is, and
the exit status is 1. persist-claude-state.sh passes no link (its refuse_links
leaves one out first), so this holds for one swapped in after that check: a
race, which so fails the run rather than pass as success.

A link that leads to no such entry (dangling, another kind, another user's, or
out of reach) is named and left as it is. A PATH that is absent or out of reach,
or no link and no KIND, is passed over. A mode that cannot be changed is named,
and the exit status is 1 once every PATH has been tried.
"""

from __future__ import annotations

import enum
import os
import stat
import sys
from pathlib import Path

# A path only: no read access needed, a link opened as itself, never inherited.
OPEN_PATH = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC

PREFIX = "persist-claude-state:"


class Kind(enum.Enum):
    """What a path is to be, by the word the caller gives, with its owner-only mode."""

    FILE = "file"
    DIRECTORY = "directory"

    def mode(self) -> int:
        return 0o700 if self is Kind.DIRECTORY else 0o600

    def holds(self, st_mode: int) -> bool:
        if self is Kind.DIRECTORY:
            return stat.S_ISDIR(st_mode)
        return stat.S_ISREG(st_mode)


def resolved_roots(candidates: list[str]) -> tuple[Path, ...]:
    """Each candidate resolved once; one that is a link, or no directory, is none."""
    roots: list[Path] = []
    for candidate in candidates:
        path = Path(candidate)
        if path.is_dir() and not path.is_symlink():
            roots.append(path.resolve())
    return tuple(roots)


def within(roots: tuple[Path, ...], target: str) -> bool:
    """Whether *target*, a resolved path, is one of *roots* or lies below one.

    A path that is not absolute, or empty, is in none.
    """
    path = Path(target)
    return path.is_absolute() and any(path.is_relative_to(root) for root in roots)


def opened_at(descriptor: int) -> str:
    """Where *descriptor* was opened, as the kernel names it; empty when unreadable."""
    try:
        return os.readlink(f"/proc/self/fd/{descriptor}")
    except OSError:
        return ""


def open_kind(kind: Kind, path: str, linked: bool) -> int | None:
    """A path-only descriptor of *path* when it is a *kind* (and, reached through a
    link, this user's own); None, with nothing left open, otherwise.

    With O_NOFOLLOW, a link swapped in after *path* was looked at opens as itself,
    which is no *kind*.
    """
    try:
        descriptor = os.open(path, OPEN_PATH)
    except OSError:
        return None
    try:
        opened = os.fstat(descriptor)
        if kind.holds(opened.st_mode) and (not linked or opened.st_uid == os.geteuid()):
            return descriptor
    except OSError:
        pass
    os.close(descriptor)
    return None


def report_outside(path: str) -> None:
    print(
        f"{PREFIX} {path} is a link that leads outside the persistent directory "
        "and ~/.claude; its mode is left as it is."
    )


def narrow(roots: tuple[Path, ...], kind: Kind, path: str) -> bool:
    """*path* set to *kind*'s mode through no link.

    False, named, when its mode could not be changed, or when it is a link that
    leads outside *roots*.
    """
    try:
        linked = stat.S_ISLNK(os.lstat(path).st_mode)
    except OSError:
        return True  # absent or out of reach: passed over
    target: str | None = path
    if linked:
        try:
            target = str(Path(path).resolve(strict=True))
        except OSError:
            target = None
        if target is not None and not within(roots, target):
            report_outside(path)
            return False
    descriptor = None if target is None else open_kind(kind, target, linked)
    # O_NOFOLLOW guards the last component alone: a parent swapped for a link
    # since the check above leads the open elsewhere, so what was opened is
    # checked again.
    if descriptor is not None and linked and not within(roots, opened_at(descriptor)):
        os.close(descriptor)
        report_outside(path)
        return False
    if descriptor is None:
        if linked:
            print(
                f"{PREFIX} {path} is a link that leads to no {kind.value} of this "
                "user's own; its mode is left as it is."
            )
        return True
    try:
        # fchmod refuses an O_PATH descriptor; a chmod through its /proc name
        # changes exactly its inode.
        if stat.S_IMODE(os.fstat(descriptor).st_mode) != kind.mode():
            os.chmod(f"/proc/self/fd/{descriptor}", kind.mode())
    except OSError as error:
        reason = "" if error.errno is None else f" ({os.strerror(error.errno)})"
        sys.stderr.write(
            f"{PREFIX} cannot narrow {path}{reason}; its mode is left as it is.\n"
        )
        return False
    finally:
        os.close(descriptor)
    return True


def main(argv: list[str]) -> int:
    if len(argv) < 3 or (len(argv) - 3) % 2:
        sys.stderr.write(f"{PREFIX} narrow.py: PERSIST CLAUDE_HOME [KIND PATH]...\n")
        return 2
    roots = resolved_roots(argv[1:3])
    pairs = argv[3:]
    results = [
        narrow(roots, Kind(pairs[index]), pairs[index + 1])
        for index in range(0, len(pairs), 2)
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
