"""Tests for .devcontainer/development/scripts/persist-claude-state.

The script keeps Claude Code's conversations, memory and settings across
Codespace rebuilds by moving an allowlist of ~/.claude entries onto the
persistent /workspaces disk and linking them back (issue #141). These tests
run the real script against a temporary home and a temporary persistent
directory: each test copies the script's directory (the script and its Python
helpers) and rewrites its persist-directory file to name its own persistent
directory, as the image's copy names /workspaces/.claude.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path

import pytest

SOURCE = (
    Path(__file__).resolve().parent.parent
    / ".devcontainer"
    / "development"
    / "scripts"
    / "persist-claude-state"
)

pytestmark = [
    pytest.mark.skipif(
        not Path("/usr/bin/python3").exists() or shutil.which("bash") is None,
        reason="needs bash and /usr/bin/python3",
    ),
    pytest.mark.skipif(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        reason="the script refuses to run as root",
    ),
]


@dataclass(frozen=True)
class Layout:
    """A temporary home, persistent directory and copy of the script."""

    script: Path
    home: Path
    persist: Path

    @property
    def claude(self) -> Path:
        return self.home / ".claude"

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run the script as the devcontainer does, with this layout's HOME."""
        return subprocess.run(
            ["/usr/bin/bash", str(self.script), *args],
            capture_output=True,
            text=True,
            env={"HOME": str(self.home), "PATH": "/usr/bin:/bin"},
            check=False,
        )


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    scripts = tmp_path / "scripts"
    shutil.copytree(SOURCE, scripts, ignore=shutil.ignore_patterns("__pycache__"))
    script = scripts / "persist-claude-state.sh"
    persist = tmp_path / "workspaces" / ".claude"
    (scripts / "persist-directory").write_text(f"{persist}\n")
    home = tmp_path / "home"
    home.mkdir()
    return Layout(script=script, home=home, persist=persist)


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def seed_state(claude: Path) -> None:
    """A ~/.claude as Claude Code leaves it: state, settings and credentials."""
    (claude / "projects" / "repo" / "memory").mkdir(parents=True)
    (claude / "projects" / "repo" / "session.jsonl").write_text('{"turn": 1}\n')
    (claude / "projects" / "repo" / "memory" / "MEMORY.md").write_text("- a fact\n")
    (claude / "file-history" / "abc").mkdir(parents=True)
    (claude / "file-history" / "abc" / "v1").write_text("checkpoint\n")
    (claude / "settings.json").write_text('{"model": "opus"}\n')
    (claude / ".credentials.json").write_text('{"token": "secret"}\n')
    (claude / "backups").mkdir()
    (claude / "backups" / ".claude.json.backup").write_text("{}\n")


def test_link_moves_the_allowlist_onto_the_persistent_disk(layout: Layout) -> None:
    seed_state(layout.claude)

    result = layout.run("link")

    assert result.returncode == 0, result.stderr
    for name in ("projects", "file-history", "settings.json", "settings.local.json"):
        entry = layout.claude / name
        assert entry.is_symlink(), name
        assert os.readlink(entry) == str(layout.persist / name)
    assert (layout.persist / "projects" / "repo" / "session.jsonl").read_text() == (
        '{"turn": 1}\n'
    )
    assert (layout.persist / "projects" / "repo" / "memory" / "MEMORY.md").exists()
    assert (layout.persist / "settings.json").read_text() == '{"model": "opus"}\n'
    # Reads through the links still work, as Claude Code's do.
    assert (layout.claude / "projects" / "repo" / "session.jsonl").exists()


def test_credentials_never_reach_the_persistent_disk(layout: Layout) -> None:
    seed_state(layout.claude)

    assert layout.run("link").returncode == 0

    assert (layout.claude / ".credentials.json").read_text() == '{"token": "secret"}\n'
    assert not (layout.persist / ".credentials.json").exists()
    assert not (layout.persist / "backups").exists()
    assert sorted(p.name for p in layout.persist.iterdir()) == [
        "file-history",
        "projects",
        "settings.json",
    ]


def test_credential_shaped_files_on_the_disk_are_removed(layout: Layout) -> None:
    layout.persist.mkdir(parents=True)
    (layout.persist / ".credentials.json").write_text("{}")
    (layout.persist / ".claude.json").write_text("{}")
    (layout.persist / "backups").mkdir()

    assert layout.run("link").returncode == 0

    for name in (".credentials.json", ".claude.json", "backups"):
        assert not (layout.persist / name).exists(), name


def test_modes_are_owner_only(layout: Layout) -> None:
    seed_state(layout.claude)
    layout.claude.chmod(0o755)

    assert layout.run("link").returncode == 0

    assert mode(layout.claude) == 0o700
    assert mode(layout.persist) == 0o700
    assert mode(layout.persist / "projects") == 0o700
    assert mode(layout.persist / "file-history") == 0o700
    assert mode(layout.persist / "settings.json") == 0o600


def test_state_survives_a_rebuild(layout: Layout) -> None:
    seed_state(layout.claude)
    assert layout.run("link").returncode == 0

    # A rebuild: the home is new, Claude Code has only signed in again.
    shutil.rmtree(layout.home)
    layout.claude.mkdir(parents=True)
    (layout.claude / ".credentials.json").write_text('{"token": "new"}\n')

    result = layout.run("link")

    assert result.returncode == 0, result.stderr
    assert (layout.claude / "projects" / "repo" / "session.jsonl").read_text() == (
        '{"turn": 1}\n'
    )
    assert (layout.claude / "settings.json").read_text() == '{"model": "opus"}\n'


def test_link_is_idempotent_and_self_healing(layout: Layout) -> None:
    seed_state(layout.claude)
    assert layout.run("link").returncode == 0
    assert layout.run("link").returncode == 0

    # An update replaces the settings link with a regular file (atomic rename).
    (layout.claude / "settings.json").unlink()
    (layout.claude / "settings.json").write_text('{"model": "sonnet"}\n')

    result = layout.run("link")

    assert result.returncode == 0, result.stderr
    assert (layout.claude / "settings.json").is_symlink()
    assert (layout.persist / "settings.json").read_text() == '{"model": "sonnet"}\n'


def test_a_linked_persistent_directory_is_refused(
    layout: Layout, tmp_path: Path
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    layout.persist.parent.mkdir(parents=True)
    layout.persist.symlink_to(elsewhere)
    seed_state(layout.claude)

    result = layout.run("link")

    assert result.returncode == 1
    assert "is a link" in result.stderr
    assert not (layout.claude / "projects").is_symlink()
    assert list(elsewhere.iterdir()) == []


@pytest.mark.parametrize("persist", ["file", "/usr"])
def test_a_persistent_directory_not_of_this_user_is_refused(
    layout: Layout, tmp_path: Path, persist: str
) -> None:
    if persist == "file":
        target = tmp_path / "not-a-directory"
        target.write_text("")
    else:
        # A directory of another user's (root's), which no non-root run owns.
        target = Path(persist)
    (layout.script.parent / "persist-directory").write_text(f"{target}\n")
    seed_state(layout.claude)

    result = layout.run("link")

    assert result.returncode == 1
    assert "is not a directory of this user's own" in result.stderr
    assert not (layout.claude / "projects").is_symlink()


def test_an_entry_holding_a_link_is_left_out(layout: Layout, tmp_path: Path) -> None:
    seed_state(layout.claude)
    target = tmp_path / "bashrc"
    target.write_text("export X=1\n")
    (layout.claude / "projects" / "repo" / "sneaky").symlink_to(target)

    result = layout.run("link")

    assert result.returncode == 1
    assert "projects is or holds a link or a special file" in result.stderr
    assert not (layout.claude / "projects").is_symlink()
    assert not (layout.persist / "projects").exists()
    # Every other entry is still persisted and linked.
    assert (layout.claude / "settings.json").is_symlink()
    assert (layout.claude / "file-history").is_symlink()
    assert target.read_text() == "export X=1\n"


def test_an_entry_holding_a_hard_link_is_left_out(
    layout: Layout, tmp_path: Path
) -> None:
    seed_state(layout.claude)
    os.link(
        layout.claude / "file-history" / "abc" / "v1",
        tmp_path / "second-name",
    )

    result = layout.run("link")

    assert result.returncode == 1
    assert "file-history is or holds a link or a special file" in result.stderr
    assert not (layout.claude / "file-history").is_symlink()
    assert (layout.claude / "projects").is_symlink()


def test_a_hard_link_inside_the_same_tree_is_kept(layout: Layout) -> None:
    seed_state(layout.claude)
    history = layout.claude / "file-history" / "abc"
    os.link(history / "v1", history / "v2")

    result = layout.run("link")

    assert result.returncode == 0, result.stderr
    assert (layout.claude / "file-history").is_symlink()
    persisted = layout.persist / "file-history" / "abc"
    assert (persisted / "v1").read_text() == "checkpoint\n"
    assert (persisted / "v2").read_text() == "checkpoint\n"
    # A second start finds the same pair, now on the persistent disk, and keeps it.
    assert layout.run("link").returncode == 0


@pytest.mark.parametrize(
    "content",
    ["relative/path\n", "/\n", "/workspaces/../etc\n", "/a\n/b\n", ""],
)
def test_an_invalid_persist_directory_stops_the_run(
    layout: Layout, content: str
) -> None:
    (layout.script.parent / "persist-directory").write_text(content)
    seed_state(layout.claude)

    result = layout.run("link")

    assert result.returncode == 1
    assert "persist-directory file is missing" in result.stderr
    assert not (layout.claude / "projects").is_symlink()


def test_snapshot_copies_without_touching_the_home(layout: Layout) -> None:
    seed_state(layout.claude)

    result = layout.run("snapshot")

    assert result.returncode == 0, result.stderr
    assert not (layout.claude / "projects").is_symlink()
    assert (layout.persist / "projects" / "repo" / "session.jsonl").exists()
    assert not (layout.persist / ".credentials.json").exists()


def test_export_archives_the_state_without_credentials(
    layout: Layout, tmp_path: Path
) -> None:
    seed_state(layout.claude)
    archive = tmp_path / "state.tgz"

    result = layout.run("export", str(archive))

    assert result.returncode == 0, result.stderr
    assert mode(archive) == 0o600
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    assert "./.claude/projects/repo/session.jsonl" in names
    assert not any("credentials" in name or "backups" in name for name in names)


def test_export_keeps_nested_names_and_only_the_allowlist(
    layout: Layout, tmp_path: Path
) -> None:
    seed_state(layout.claude)
    nested = layout.claude / "projects" / "-workspaces-backups"
    nested.mkdir()
    (nested / "session.jsonl").write_text("{}\n")
    layout.persist.mkdir(parents=True)
    (layout.persist / "stray.txt").write_text("not allowlisted\n")
    (layout.persist / "stray-link").symlink_to(tmp_path)
    archive = tmp_path / "state.tgz"

    result = layout.run("export", str(archive))

    assert result.returncode == 0, result.stderr
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    assert "./.claude/projects/-workspaces-backups/session.jsonl" in names
    assert not any("stray" in name for name in names)


def test_export_without_a_left_out_entry_says_so(
    layout: Layout, tmp_path: Path
) -> None:
    seed_state(layout.claude)
    (layout.claude / "projects" / "repo" / "sneaky").symlink_to(tmp_path)
    archive = tmp_path / "state.tgz"

    result = layout.run("export", str(archive))

    assert result.returncode == 1
    assert "without projects" in result.stdout
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    assert not any("/projects" in name for name in names)
    assert "./.claude/file-history/abc/v1" in names


def test_unknown_mode_is_rejected(layout: Layout) -> None:
    result = layout.run("bogus")

    assert result.returncode == 2
    assert "usage:" in result.stderr
