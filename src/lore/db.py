"""SQLite database layer with FTS5 full-text search."""

import json
import sqlite3
from pathlib import Path

from lore.models import Entry, FileLink


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    content     TEXT    NOT NULL,
    tags        TEXT    NOT NULL DEFAULT '[]',
    git_hash    TEXT,
    git_branch  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    importance  INTEGER NOT NULL DEFAULT 5,
    category    TEXT    NOT NULL DEFAULT 'other'
);

CREATE TABLE IF NOT EXISTS file_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    file_path   TEXT    NOT NULL,
    note        TEXT    NOT NULL DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
    content,
    tags,
    content='entries',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO fts(rowid, content, tags) VALUES (new.id, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO fts(fts, rowid, content, tags) VALUES ('delete', old.id, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO fts(fts, rowid, content, tags) VALUES ('delete', old.id, old.content, old.tags);
    INSERT INTO fts(rowid, content, tags) VALUES (new.id, new.content, new.tags);
END;
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _row_to_entry(row: sqlite3.Row) -> Entry:
    return Entry(
        id=row["id"],
        content=row["content"],
        tags=json.loads(row["tags"]),
        git_hash=row["git_hash"],
        git_branch=row["git_branch"],
        created_at=row["created_at"],
        importance=row["importance"],
        category=row["category"],
    )


def add_entry(
    db_path: Path,
    content: str,
    tags: list[str],
    git_hash: str | None,
    git_branch: str | None,
    importance: int,
    category: str,
    files: list[tuple[str, str]] | None = None,  # [(file_path, note), ...]
) -> Entry:
    """Insert a new entry and optional file links, return the created Entry."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO entries (content, tags, git_hash, git_branch, importance, category)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (content, json.dumps(tags), git_hash, git_branch, importance, category),
        )
        entry_id = cur.lastrowid
        if files:
            conn.executemany(
                "INSERT INTO file_links (entry_id, file_path, note) VALUES (?, ?, ?)",
                [(entry_id, fp, note) for fp, note in files],
            )
        conn.commit()
        row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
        return _row_to_entry(row)


def get_entry(db_path: Path, entry_id: int) -> Entry | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
        return _row_to_entry(row) if row else None


def list_entries(
    db_path: Path,
    tag: str | None = None,
    limit: int = 50,
) -> list[Entry]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM entries ORDER BY created_at DESC",
        ).fetchall()
        entries = [_row_to_entry(r) for r in rows]
        if tag:
            entries = [e for e in entries if tag in e.tags]
        return entries[:limit]


def delete_entry(db_path: Path, entry_id: int) -> bool:
    """Delete an entry (cascades to file_links). Returns True if deleted."""
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        conn.commit()
        return cur.rowcount > 0


def add_file_link(db_path: Path, entry_id: int, file_path: str, note: str) -> FileLink:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO file_links (entry_id, file_path, note) VALUES (?, ?, ?)",
            (entry_id, file_path, note),
        )
        conn.commit()
        return FileLink(id=cur.lastrowid, entry_id=entry_id, file_path=file_path, note=note)


def get_file_links(db_path: Path, entry_id: int) -> list[FileLink]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM file_links WHERE entry_id = ?", (entry_id,)
        ).fetchall()
        return [FileLink(id=r["id"], entry_id=r["entry_id"], file_path=r["file_path"], note=r["note"]) for r in rows]


def get_entries_by_file(db_path: Path, file_path: str) -> list[tuple[Entry, FileLink]]:
    """Return all (entry, file_link) pairs for a given file path."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT e.*, fl.id as fl_id, fl.file_path, fl.note
            FROM entries e
            JOIN file_links fl ON fl.entry_id = e.id
            WHERE fl.file_path = ?
            ORDER BY e.created_at DESC
            """,
            (file_path,),
        ).fetchall()
        result = []
        for r in rows:
            entry = Entry(
                id=r["id"], content=r["content"], tags=json.loads(r["tags"]),
                git_hash=r["git_hash"], git_branch=r["git_branch"],
                created_at=r["created_at"], importance=r["importance"], category=r["category"],
            )
            fl = FileLink(id=r["fl_id"], entry_id=r["id"], file_path=r["file_path"], note=r["note"])
            result.append((entry, fl))
        return result


def fts_search(db_path: Path, fts_query: str, limit: int = 20) -> list[tuple[Entry, float]]:
    """FTS5 BM25 search. Returns (entry, bm25_score) sorted best-first."""
    with _connect(db_path) as conn:
        try:
            rows = conn.execute(
                """
                SELECT e.*, bm25(fts) as score
                FROM fts
                JOIN entries e ON fts.rowid = e.id
                WHERE fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            # Bad FTS query syntax - return empty
            return []
        return [(_row_to_entry(r), float(r["score"])) for r in rows]


def get_top_entries(db_path: Path, limit: int = 10) -> list[Entry]:
    """Return top entries by importance for MEMORY.md sync."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM entries ORDER BY importance DESC, created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_entry(r) for r in rows]
