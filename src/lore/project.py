"""Git root detection and database path resolution."""

import os
import subprocess
from pathlib import Path


def get_git_root(start: Path | None = None) -> Path | None:
    """Walk up from start (or cwd) to find the nearest .git directory."""
    start = start or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_project_name(start: Path | None = None) -> str:
    """Return project name: git root basename, or cwd basename as fallback."""
    root = get_git_root(start)
    if root:
        return root.name
    return (start or Path.cwd()).name


def get_db_path(project_name: str | None = None) -> Path:
    """Return ~/.lore/<project-name>.db, creating the directory if needed."""
    name = project_name or get_project_name()
    lore_dir = Path.home() / ".lore"
    lore_dir.mkdir(exist_ok=True)
    return lore_dir / f"{name}.db"


def get_git_info() -> dict[str, str | None]:
    """Return current git hash and branch, or None values if not in a repo."""
    try:
        git_hash = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        git_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return {"git_hash": git_hash, "git_branch": git_branch}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"git_hash": None, "git_branch": None}
