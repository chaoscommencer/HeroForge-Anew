"""Tests for .github/scripts/pick-devcontainer-image.sh.

The script chooses which devcontainers/python base image the
update-devcontainer workflow proposes. These tests run it against small,
hand-written MCR catalogs and Dockerfiles, covering the review findings it
fixes: never propose a downgrade, age-gate on MCR's own listing date, and skip
(rather than crash on) malformed catalog rows.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "scripts"
    / "pick-devcontainer-image.sh"
)

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="needs bash and jq",
)

# Fixed "now" for every test: 2026-11-14T00:00:00Z.
NOW = int(datetime(2026, 11, 14, tzinfo=UTC).timestamp())


def digest(char: str) -> str:
    """Return a well-formed sha256 digest made of one repeated hex character."""
    return "sha256:" + char * 64


def tag(name: str, char: str, created: str) -> dict[str, Any]:
    """Return one MCR catalog row in the shape the real API uses."""
    return {
        "name": name,
        "digest": digest(char),
        "createdDate": f"{created}T10:00:00.0000000+00:00",
        "repository": "devcontainers/python",
    }


def run_picker(
    tmp_path: Path,
    from_tag: str,
    from_digest: str,
    catalog: Any,
    **env: str,
) -> subprocess.CompletedProcess[str]:
    """Run the picker on a Dockerfile pinned to from_tag@from_digest."""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        "# syntax=docker/dockerfile:1\n"
        f"FROM mcr.microsoft.com/devcontainers/python:{from_tag}@{from_digest}\n"
    )
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text(json.dumps(catalog))
    return subprocess.run(
        ["bash", str(SCRIPT), str(dockerfile), str(catalog_file)],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "NOW": str(NOW), **env},
        check=False,
    )


def outputs(result: subprocess.CompletedProcess[str]) -> dict[str, str]:
    """Parse the picker's key=value stdout lines."""
    return dict(line.split("=", 1) for line in result.stdout.splitlines())


CATALOG = [
    tag("3.0.8-3.12-bookworm", "a", "2026-05-18"),
    tag("3-3.12-bookworm", "a", "2025-11-27"),  # floating tag, same digest
    tag("3.3.1-3.12-bookworm", "b", "2026-10-29"),
    tag("3.3.2-3.12-bookworm", "c", "2026-10-28"),  # listed before 3.3.1
    tag("3.3.3-3.12-bookworm", "d", "2026-11-13"),  # too recent
    tag("3.4.0-3.13-bookworm", "e", "2026-01-01"),  # other Python minor
    tag("4.0.0-3.12-bookworm", "f", "2026-01-01"),  # other image major
]


def test_floating_pin_is_resolved_through_its_digest(tmp_path: Path) -> None:
    result = run_picker(tmp_path, "3-3.12-bookworm", digest("a"), CATALOG)

    assert result.returncode == 0, result.stderr
    assert outputs(result) == {
        "current_version": "3.0.8",
        "has_updates": "true",
        "tag": "3.3.2-3.12-bookworm",
        "digest": digest("c"),
        "created": "2026-10-28T10:00:00.0000000+00:00",
    }


def test_too_recent_images_are_skipped_unless_allowed(tmp_path: Path) -> None:
    result = run_picker(
        tmp_path, "3.0.8-3.12-bookworm", digest("a"), CATALOG, ALLOW_RECENT="true"
    )

    assert result.returncode == 0, result.stderr
    assert outputs(result)["tag"] == "3.3.3-3.12-bookworm"


def test_never_proposes_a_downgrade(tmp_path: Path) -> None:
    # 3.3.3 was taken early with ALLOW_RECENT; the next scheduled run must not
    # "update" back to 3.3.2, the newest image old enough for the age rule.
    result = run_picker(tmp_path, "3.3.3-3.12-bookworm", digest("d"), CATALOG)

    assert result.returncode == 0, result.stderr
    assert outputs(result) == {"current_version": "3.3.3", "has_updates": "false"}


def test_versions_compare_numerically(tmp_path: Path) -> None:
    catalog = [
        tag("3.9.0-3.12-bookworm", "a", "2026-01-01"),
        tag("3.10.0-3.12-bookworm", "b", "2026-02-01"),
    ]

    result = run_picker(tmp_path, "3.9.0-3.12-bookworm", digest("a"), catalog)

    assert outputs(result)["tag"] == "3.10.0-3.12-bookworm"


def test_age_rule_uses_the_catalog_listing_date(tmp_path: Path) -> None:
    catalog = [
        tag("3.0.8-3.12-bookworm", "a", "2026-05-18"),
        tag("3.3.0-3.12-bookworm", "b", "2026-10-31"),  # 13.6 days before NOW
    ]

    result = run_picker(tmp_path, "3.0.8-3.12-bookworm", digest("a"), catalog)
    assert outputs(result)["has_updates"] == "false"

    result = run_picker(
        tmp_path, "3.0.8-3.12-bookworm", digest("a"), catalog, MIN_AGE_DAYS="13"
    )
    assert outputs(result)["tag"] == "3.3.0-3.12-bookworm"


def test_malformed_rows_are_skipped(tmp_path: Path) -> None:
    catalog = [
        tag("3.0.8-3.12-bookworm", "a", "2026-05-18"),
        "not an object",
        {"name": 42, "digest": digest("b")},
        {"name": "3.5.0-3.12-bookworm", "digest": "sha256:short"},
        {"name": "3.6.0-3.12-bookworm", "digest": digest("c")},  # no date
        {**tag("3.7.0-3.12-bookworm", "e", "x"), "createdDate": "yesterday"},
        tag("3.1.0-3.12-bookworm", "f", "2026-06-01"),
    ]

    result = run_picker(tmp_path, "3.0.8-3.12-bookworm", digest("a"), catalog)

    assert result.returncode == 0, result.stderr
    assert outputs(result)["tag"] == "3.1.0-3.12-bookworm"


def test_unknown_floating_digest_fails_safely(tmp_path: Path) -> None:
    result = run_picker(tmp_path, "3-3.12-bookworm", digest("9"), CATALOG)

    assert result.returncode != 0
    assert result.stdout == ""
    assert "pin a versioned tag" in result.stderr


@pytest.mark.parametrize(
    "catalog",
    [{"not": "an array"}, "garbage"],
)
def test_catalog_that_is_not_an_array_fails_safely(
    tmp_path: Path, catalog: Any
) -> None:
    result = run_picker(tmp_path, "3.0.8-3.12-bookworm", digest("a"), catalog)

    assert result.returncode != 0
    assert result.stdout == ""


def test_unpinned_from_line_fails_safely(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM mcr.microsoft.com/devcontainers/python:3-3.12\n")
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text(json.dumps(CATALOG))

    result = subprocess.run(
        ["bash", str(SCRIPT), str(dockerfile), str(catalog_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "no pinned devcontainers/python FROM line" in result.stderr
