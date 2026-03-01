"""Click CLI entry point for lore."""

import sys
from pathlib import Path

import click

from lore import claude, db, search, ui
from lore.project import get_db_path, get_git_info
from lore.sync import sync_memory


@click.group()
@click.version_option()
def cli():
    """lore — local semantic knowledge management for developers."""


@cli.command()
def help():
    """Show all commands and options."""
    ui.render_help()


@cli.command()
@click.argument("content")
@click.option("--file", "-f", "files", multiple=True, metavar="FILE",
              help="Link this entry to a file path (can repeat).")
@click.option("--tag", "-t", "extra_tags", multiple=True,
              help="Additional tags (Claude also extracts tags automatically).")
def add(content: str, files: tuple, extra_tags: tuple):
    """Add a new knowledge entry."""
    db_path = get_db_path()
    git_info = get_git_info()

    # Claude tag extraction (with graceful fallback)
    metadata = claude.extract_tags(content)
    if metadata:
        tags = list(dict.fromkeys(metadata.get("tags", []) + list(extra_tags)))
        importance = int(metadata.get("importance", 5))
        category = metadata.get("category", "other")
    else:
        tags = list(extra_tags)
        importance = 5
        category = "other"

    file_pairs = [(f, "") for f in files] if files else None

    entry = db.add_entry(
        db_path=db_path,
        content=content,
        tags=tags,
        git_hash=git_info["git_hash"],
        git_branch=git_info["git_branch"],
        importance=importance,
        category=category,
        files=file_pairs,
    )
    ui.render_entry_added(entry)


@cli.command()
@click.argument("query")
def find(query: str):
    """Semantic search over all entries."""
    db_path = get_db_path()
    results = search.search(db_path, query)
    ui.render_search_results(results, query)


@cli.command()
@click.argument("topic")
def why(topic: str):
    """Explain why a decision was made (shorthand for find)."""
    db_path = get_db_path()
    results = search.search(db_path, f"why {topic}")
    ui.render_search_results(results, f"why {topic}")


@cli.command("list")
@click.option("--tag", "-t", default=None, help="Filter by tag.")
@click.option("--limit", "-n", default=20, show_default=True, help="Max entries.")
def list_cmd(tag: str | None, limit: int):
    """List recent entries."""
    db_path = get_db_path()
    entries = db.list_entries(db_path, tag=tag, limit=limit)
    ui.render_entries_table(entries)


@cli.command()
@click.argument("entry_id", type=int)
def show(entry_id: int):
    """Show full detail for an entry."""
    db_path = get_db_path()
    entry = db.get_entry(db_path, entry_id)
    if not entry:
        ui.render_error(f"No entry with ID {entry_id}.")
        sys.exit(1)
    file_links = db.get_file_links(db_path, entry_id)
    ui.render_entry_detail(entry, file_links)


@cli.command()
@click.argument("entry_id", type=int)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def delete(entry_id: int, yes: bool):
    """Delete an entry (with confirmation)."""
    db_path = get_db_path()
    entry = db.get_entry(db_path, entry_id)
    if not entry:
        ui.render_error(f"No entry with ID {entry_id}.")
        sys.exit(1)
    ui.render_confirm_delete(entry)
    if not yes:
        click.confirm("Delete this entry?", abort=True)
    if db.delete_entry(db_path, entry_id):
        click.echo(f"Deleted entry #{entry_id}.")
    else:
        ui.render_error("Delete failed.")
        sys.exit(1)


@cli.command()
@click.argument("file_path")
@click.argument("entry_id", type=int)
@click.option("--note", "-n", default="", help="Note about why this file is linked.")
def link(file_path: str, entry_id: int, note: str):
    """Link a file to an existing entry."""
    db_path = get_db_path()
    entry = db.get_entry(db_path, entry_id)
    if not entry:
        ui.render_error(f"No entry with ID {entry_id}.")
        sys.exit(1)
    db.add_file_link(db_path, entry_id, file_path, note)
    ui.render_file_link_added(file_path, entry_id, note)


@cli.command()
@click.argument("file_path")
def files(file_path: str):
    """Show all entries linked to a file."""
    db_path = get_db_path()
    pairs = db.get_entries_by_file(db_path, file_path)
    ui.render_file_entries(file_path, pairs)


@cli.command()
@click.option("--output", "-o", default=None, metavar="FILE",
              help="Write to file instead of stdout.")
def export(output: str | None):
    """Export all entries as Markdown."""
    db_path = get_db_path()
    entries = db.list_entries(db_path, limit=10000)
    lines = ["# lore — Project Knowledge Base\n"]
    for e in entries:
        lines.append(f"## [{e.id}] {e.content[:80]}")
        lines.append(f"**Category:** {e.category}  **Importance:** {e.importance}/10  "
                     f"**Date:** {e.created_at[:10]}")
        if e.tags:
            lines.append(f"**Tags:** {', '.join(e.tags)}")
        lines.append("")
        lines.append(e.content)
        file_links = db.get_file_links(db_path, e.id)
        if file_links:
            lines.append("")
            lines.append("**Files:**")
            for fl in file_links:
                lines.append(f"- `{fl.file_path}`" + (f" — {fl.note}" if fl.note else ""))
        lines.append("")
        lines.append("---")
        lines.append("")
    content = "\n".join(lines)
    if output:
        Path(output).write_text(content)
        click.echo(f"Exported to {output}")
    else:
        click.echo(content)


@cli.command()
@click.option("--dry-run", is_flag=True, help="Preview without writing.")
@click.option("--top", default=10, show_default=True,
              help="Number of top entries to include.")
def sync(dry_run: bool, top: int):
    """Sync top entries to MEMORY.md."""
    db_path = get_db_path()
    entries = db.get_top_entries(db_path, limit=top)
    if not entries:
        click.echo("No entries to sync.")
        return

    entry_dicts = [
        {"content": e.content, "tags": e.tags, "category": e.category, "importance": e.importance}
        for e in entries
    ]
    section = claude.generate_memory_summary(entry_dicts)

    if section is None:
        # Fallback: generate a simple summary without Claude
        section = "## Project Decisions (via lore)\n\n"
        for e in entries:
            section += f"- [{e.category}] {e.content}\n"

    full_section = f"<!-- lore:start -->\n{section}\n<!-- lore:end -->"

    if dry_run:
        ui.render_sync_preview(full_section)
        return

    memory_path = sync_memory(full_section)
    ui.render_sync_done(str(memory_path))
