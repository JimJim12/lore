"""Rich terminal UI rendering for all lore commands."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from lore.models import Entry, FileLink, SearchResult

console = Console()


def _tag_str(tags: list[str]) -> str:
    return " ".join(f"[cyan]#{t}[/cyan]" for t in tags) if tags else "[dim]none[/dim]"


def _importance_bar(importance: int) -> str:
    filled = "█" * importance
    empty = "░" * (10 - importance)
    color = "green" if importance >= 7 else "yellow" if importance >= 4 else "red"
    return f"[{color}]{filled}[/{color}][dim]{empty}[/dim] {importance}/10"


def render_entry_added(entry: Entry) -> None:
    console.print(
        Panel(
            f"[bold]{entry.content}[/bold]\n\n"
            f"Tags: {_tag_str(entry.tags)}\n"
            f"Category: [magenta]{entry.category}[/magenta]  "
            f"Importance: {_importance_bar(entry.importance)}\n"
            f"ID: [dim]{entry.id}[/dim]  Branch: [dim]{entry.git_branch or 'n/a'}[/dim]",
            title="[green]Entry added[/green]",
            border_style="green",
        )
    )


def render_entry_detail(entry: Entry, file_links: list[FileLink]) -> None:
    lines = [
        f"[bold]{entry.content}[/bold]",
        "",
        f"Tags:      {_tag_str(entry.tags)}",
        f"Category:  [magenta]{entry.category}[/magenta]",
        f"Importance: {_importance_bar(entry.importance)}",
        f"Created:   [dim]{entry.created_at}[/dim]",
        f"Git:       [dim]{entry.git_branch or 'n/a'} @ {entry.git_hash or 'n/a'}[/dim]",
    ]
    if file_links:
        lines.append("")
        lines.append("Files:")
        for fl in file_links:
            note = f" — {fl.note}" if fl.note else ""
            lines.append(f"  [blue]{fl.file_path}[/blue]{note}")
    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold]Entry #{entry.id}[/bold]",
            border_style="blue",
        )
    )


def render_entries_table(entries: list[Entry]) -> None:
    if not entries:
        console.print("[dim]No entries found.[/dim]")
        return
    table = Table(box=box.ROUNDED, show_lines=False, highlight=True)
    table.add_column("ID", style="dim", width=5, justify="right")
    table.add_column("Imp", width=4, justify="center")
    table.add_column("Category", width=12)
    table.add_column("Content", ratio=1)
    table.add_column("Tags", width=24)
    table.add_column("Date", width=10, style="dim")
    for e in entries:
        imp_color = "green" if e.importance >= 7 else "yellow" if e.importance >= 4 else "red"
        table.add_row(
            str(e.id),
            f"[{imp_color}]{e.importance}[/{imp_color}]",
            f"[magenta]{e.category}[/magenta]",
            e.content[:80] + ("…" if len(e.content) > 80 else ""),
            " ".join(f"#{t}" for t in e.tags[:4]),
            e.created_at[:10],
        )
    console.print(table)


def render_search_results(results: list[SearchResult], query: str) -> None:
    if not results:
        console.print(f"[dim]No results for '{query}'.[/dim]")
        return
    console.print(f"\n[bold]Search results for:[/bold] [italic]{query}[/italic]\n")
    for i, r in enumerate(results, 1):
        score_pct = f"{r.score * 100:.0f}%"
        reason_line = f"\n[italic dim]{r.reason}[/italic dim]" if r.reason else ""
        tags_line = _tag_str(r.entry.tags)
        console.print(
            Panel(
                f"{r.entry.content}{reason_line}\n\n"
                f"Tags: {tags_line}  "
                f"[dim]#{r.entry.id} · {r.entry.category} · {r.entry.created_at[:10]}[/dim]",
                title=f"[bold]#{i}[/bold] [green]{score_pct} relevance[/green]",
                border_style="bright_black",
            )
        )


def render_file_entries(file_path: str, pairs: list[tuple]) -> None:
    if not pairs:
        console.print(f"[dim]No entries linked to {file_path}.[/dim]")
        return
    console.print(f"\n[bold]Entries for:[/bold] [blue]{file_path}[/blue]\n")
    for entry, fl in pairs:
        note = f"[dim]{fl.note}[/dim]\n" if fl.note else ""
        console.print(
            Panel(
                f"{note}{entry.content}\n\n"
                f"Tags: {_tag_str(entry.tags)}  "
                f"[dim]#{entry.id} · {entry.created_at[:10]}[/dim]",
                border_style="blue",
            )
        )


def render_file_link_added(file_path: str, entry_id: int, note: str) -> None:
    console.print(
        f"[green]Linked[/green] [blue]{file_path}[/blue] → entry #{entry_id}"
        + (f" ({note})" if note else "")
    )


def render_sync_preview(section: str) -> None:
    console.print(Panel(section, title="[yellow]MEMORY.md preview (dry run)[/yellow]", border_style="yellow"))


def render_sync_done(path: str) -> None:
    console.print(f"[green]Synced[/green] → {path}")


def render_error(message: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {message}")


def render_help() -> None:
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column(style="dim", no_wrap=True)
    table.add_column()

    commands = [
        ("add",    "<note>",              "Save a decision. Claude extracts tags, importance, and category."),
        ("",       "--file/-f <path>",    "Link to a file (repeatable)"),
        ("",       "--tag/-t <tag>",      "Add a tag manually"),
        ("find",   "<query>",             "Semantic search. Claude expands query and re-ranks results."),
        ("why",    "<topic>",             "Shorthand for find, framed as 'why <topic>'"),
        ("list",   "",                    "Recent entries table"),
        ("",       "--tag/-t <tag>",      "Filter by tag"),
        ("",       "--limit/-n <n>",      "Max rows (default 20)"),
        ("show",   "<id>",               "Full detail for one entry"),
        ("delete", "<id>",               "Delete an entry (prompts to confirm)"),
        ("",       "--yes/-y",            "Skip confirmation"),
        ("link",   "<path> <id>",         "Link a file to an existing entry"),
        ("",       "--note/-n <text>",    "Describe why the file is relevant"),
        ("files",  "<path>",             "All entries linked to a file"),
        ("export", "",                    "Dump all entries as Markdown"),
        ("",       "--output/-o <file>",  "Write to file instead of stdout"),
        ("sync",   "",                    "Write top entries to MEMORY.md"),
        ("",       "--dry-run",           "Preview without writing"),
        ("",       "--top <n>",           "Number of entries to include (default 10)"),
    ]

    for cmd, args, desc in commands:
        table.add_row(cmd, args, desc)

    console.print()
    console.print(Panel(
        table,
        title="[bold]lore[/bold] — local knowledge management for developers",
        subtitle="[dim]lore <command> --help for full options[/dim]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()


def render_confirm_delete(entry: Entry) -> None:
    console.print(
        Panel(
            entry.content[:200],
            title=f"[red]Delete entry #{entry.id}?[/red]",
            border_style="red",
        )
    )
