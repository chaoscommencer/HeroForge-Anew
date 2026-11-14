"""Print the persistent directory named in a persist-claude-state path file.

persist-claude-state.sh runs this on the system Python in isolated mode
(``/usr/bin/python3 -I -S -B``), passing the path of a file that sits beside it
in the image's root-owned, read-only tree. The file must hold exactly one line:
an absolute, normalized path with no ``..``, no control character, no trailing
slash, and not ``/`` itself. The path is printed (without a newline) and the
exit status is 0; for anything else, including a missing file, a link or no
regular file, nothing is printed and the exit status is 1.
"""

from __future__ import annotations

import os
import posixpath
import stat
import sys

# One line of at most this many bytes; a longer file is no path file.
MAX_BYTES = 4096


def read_line(path: str) -> bytes | None:
    """The raw content of the regular file at *path*, read through no link.

    None when it is missing, a link, no regular file, or longer than MAX_BYTES.
    """
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        )
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        raw = os.read(descriptor, MAX_BYTES + 1)
    finally:
        os.close(descriptor)
    return raw if len(raw) <= MAX_BYTES else None


def is_valid(value: str) -> bool:
    """Whether *value* is an absolute, normalized path that is not ``/``.

    ``//`` is checked apart, because normpath keeps a leading ``//``.
    """
    return (
        value.isprintable()
        and value.startswith("/")
        and value != "/"
        and not value.endswith("/")
        and "//" not in value
        and posixpath.normpath(value) == value
        and ".." not in value.split("/")
    )


def persist_directory(path: str) -> str | None:
    """The one path the file at *path* names, or None when it names no valid one."""
    raw = read_line(path)
    if raw is None:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    value = text[:-1] if text.endswith("\n") else text
    return value if is_valid(value) else None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return 1
    directory = persist_directory(argv[1])
    if directory is None:
        return 1
    sys.stdout.write(directory)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
