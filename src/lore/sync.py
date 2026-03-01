"""MEMORY.md read/write for lore sync command."""

import re
from pathlib import Path

MEMORY_PATH = Path.home() / ".claude/projects/-home-loljk-projects-cloudopsjobs/memory/MEMORY.md"

LORE_START = "<!-- lore:start -->"
LORE_END = "<!-- lore:end -->"
_BLOCK_RE = re.compile(
    r"<!-- lore:start -->.*?<!-- lore:end -->",
    re.DOTALL,
)


def sync_memory(section: str, memory_path: Path | None = None) -> Path:
    """
    Write the lore section into MEMORY.md.
    Replaces an existing <!-- lore:start -->...<!-- lore:end --> block,
    or appends it if not present. Creates the file and directory if needed.
    Returns the path written.
    """
    path = memory_path or MEMORY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = path.read_text(encoding="utf-8") if path.exists() else ""

    if _BLOCK_RE.search(existing):
        updated = _BLOCK_RE.sub(section, existing)
    else:
        updated = existing.rstrip() + ("\n\n" if existing else "") + section + "\n"

    path.write_text(updated, encoding="utf-8")
    return path
