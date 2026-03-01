"""Data models for lore."""

from dataclasses import dataclass, field


@dataclass
class Entry:
    id: int
    content: str
    tags: list[str]
    git_hash: str | None
    git_branch: str | None
    created_at: str
    importance: int
    category: str


@dataclass
class FileLink:
    id: int
    entry_id: int
    file_path: str
    note: str


@dataclass
class SearchResult:
    entry: Entry
    score: float
    reason: str | None = None  # set by Claude re-ranker
