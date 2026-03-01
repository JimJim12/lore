"""All Anthropic API calls. Every function returns None on any failure."""

import json
import os

from dotenv import load_dotenv

load_dotenv()  # loads .env from cwd or any parent directory

MODEL = "claude-haiku-4-5-20251001"


def _client():
    """Return an Anthropic client, or None if SDK/key unavailable."""
    try:
        import anthropic  # noqa: PLC0415
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return None
        return anthropic.Anthropic(api_key=key)
    except ImportError:
        return None


def extract_tags(content: str) -> dict | None:
    """
    Extract tags, importance (0-10), and category from content.
    Returns: {"tags": [...], "importance": int, "category": str}
    """
    client = _client()
    if client is None:
        return None
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=(
                "You extract metadata from developer notes about architectural decisions. "
                "Respond ONLY with valid JSON, no explanation."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Extract metadata from this developer note:\n\n{content}\n\n"
                        "Return JSON: "
                        '{"tags": ["tag1", "tag2"], "importance": 7, "category": "architecture"}\n'
                        "Categories: architecture, security, performance, database, api, testing, devops, other\n"
                        "Importance: 0=trivial, 10=critical decision"
                    ),
                }
            ],
        )
        text = resp.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return None


def expand_query(query: str) -> dict | None:
    """
    Expand a search query into FTS5-friendly terms.
    Returns: {"primary_terms": [...], "expanded_terms": [...]}
    """
    client = _client()
    if client is None:
        return None
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=(
                "You expand developer search queries into synonyms and related terms "
                "for full-text search. Respond ONLY with valid JSON."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Expand this search query for a developer knowledge base: '{query}'\n\n"
                        "Return JSON: "
                        '{"primary_terms": ["jwt"], "expanded_terms": ["token", "stateless", "auth", "session"]}\n'
                        "Include 3-6 expanded terms that are synonyms or closely related concepts."
                    ),
                }
            ],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return None


def rerank(query: str, candidates: list[dict]) -> list[dict] | None:
    """
    Re-rank search candidates by relevance to query.
    candidates: [{"id": int, "content": str, "tags": [...]}]
    Returns: [{"id": int, "score": float, "reason": str}] ordered best-first.
    """
    if not candidates:
        return None
    client = _client()
    if client is None:
        return None
    try:
        candidates_text = "\n\n".join(
            f"ID {c['id']}: {c['content'][:300]}" for c in candidates
        )
        resp = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=(
                "You re-rank developer knowledge base entries by relevance to a query. "
                "Respond ONLY with valid JSON."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Query: '{query}'\n\nCandidates:\n{candidates_text}\n\n"
                        "Score each candidate 0.0-1.0 by relevance to the query. "
                        "Return JSON array sorted best-first:\n"
                        '[{"id": 3, "score": 0.95, "reason": "Directly explains JWT choice"}, ...]'
                    ),
                }
            ],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return None


def generate_memory_summary(entries: list[dict]) -> str | None:
    """
    Generate a MEMORY.md section from top entries.
    entries: [{"content": str, "tags": [...], "category": str, "importance": int}]
    Returns a markdown string or None.
    """
    if not entries:
        return None
    client = _client()
    if client is None:
        return None
    try:
        entries_text = "\n\n".join(
            f"[{e.get('category', 'other')}] {e['content']}" for e in entries
        )
        resp = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=(
                "You write concise MEMORY.md sections for Claude Code sessions. "
                "Focus on decisions and reasoning, not descriptions."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Write a '## Project Decisions (via lore)' section for MEMORY.md "
                        "from these architectural decisions. Be concise and actionable "
                        "(max 300 words). Use bullet points.\n\n"
                        f"Decisions:\n{entries_text}"
                    ),
                }
            ],
        )
        return resp.content[0].text.strip()
    except Exception:
        return None
