"""Two-phase search: FTS5 BM25 recall + Claude re-ranking."""

from pathlib import Path

from lore import claude, db
from lore.models import Entry, SearchResult


def _build_fts_query(primary: list[str], expanded: list[str]) -> str:
    """Build an FTS5 OR query from primary and expanded terms."""
    all_terms = list(dict.fromkeys(primary + expanded))  # deduplicate, preserve order
    # Quote multi-word terms, escape single words
    parts = []
    for term in all_terms:
        clean = term.replace('"', "").strip()
        if clean:
            parts.append(f'"{clean}"')
    return " OR ".join(parts) if parts else " OR ".join(f'"{t}"' for t in all_terms)


_STOP_WORDS = {"why", "did", "we", "do", "is", "the", "a", "an", "for", "to",
               "how", "what", "when", "where", "which", "who", "pick", "use",
               "chose", "choose", "should", "would", "could", "about", "our"}


def _fallback_fts_query(query: str) -> str:
    """Build an OR prefix query from non-stop-words for no-Claude fallback."""
    words = [w.strip("?.,!") for w in query.lower().split()]
    terms = [f'"{w}"*' for w in words if w and w not in _STOP_WORDS]
    return " OR ".join(terms) if terms else f'"{query}"'


def search(db_path: Path, query: str, limit: int = 10) -> list[SearchResult]:
    """
    Run the two-phase search pipeline:
    1. Claude query expansion -> FTS5 BM25 recall (up to 20 candidates)
    2. Claude re-ranking of candidates
    Falls back gracefully at each step if Claude is unavailable.
    """
    # Phase 1: query expansion
    fts_query = _fallback_fts_query(query)  # start with smart fallback
    expansion = claude.expand_query(query)
    if expansion:
        primary = expansion.get("primary_terms", [query])
        expanded = expansion.get("expanded_terms", [])
        fts_query = _build_fts_query(primary, expanded)

    # Phase 2: FTS5 recall
    candidates = db.fts_search(db_path, fts_query, limit=20)

    if not candidates:
        # Try raw query as fallback if expansion produced no results
        if expansion:
            candidates = db.fts_search(db_path, query, limit=20)

    if not candidates:
        return []

    # Phase 3: Claude re-ranking
    candidate_dicts = [
        {"id": entry.id, "content": entry.content, "tags": entry.tags}
        for entry, _ in candidates
    ]
    reranked = claude.rerank(query, candidate_dicts)

    entry_map: dict[int, Entry] = {entry.id: entry for entry, _ in candidates}

    if reranked:
        results = []
        for item in reranked[:limit]:
            entry = entry_map.get(item["id"])
            if entry:
                results.append(
                    SearchResult(
                        entry=entry,
                        score=float(item.get("score", 0.5)),
                        reason=item.get("reason"),
                    )
                )
        return results
    else:
        # No Claude: return BM25 results (score is negative BM25, lower=better)
        bm25_results = sorted(candidates, key=lambda x: x[1])
        return [
            SearchResult(entry=entry, score=1.0 / (i + 1), reason=None)
            for i, (entry, _) in enumerate(bm25_results[:limit])
        ]
