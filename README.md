# lore

Capture the *why* behind your code. `lore` stores architectural decisions and technical reasoning in a local SQLite database, and uses Claude to make them semantically searchable.

```
$ lore add "JWT for auth — need stateless auth for mobile clients" --file src/auth/middleware.ts
$ lore find "why did we pick JWT"
╭─── #1  95% relevance ────────────────────────────────────────────╮
│ JWT for auth — need stateless auth for mobile clients            │
│ Directly addresses stateless authentication decision             │
│ Tags: #auth #jwt #mobile  · #2 · security · 2026-03-01          │
╰──────────────────────────────────────────────────────────────────╯
```

---

## How it works

1. **Add a note** — `lore add "..."` stores it in `~/.lore/<project>.db` and asks Claude to extract tags, importance (0–10), and category.
2. **Search** — `lore find "..."` expands your query with Claude (synonyms, related terms), runs FTS5 BM25 recall over the database, then re-ranks results with Claude for relevance.
3. **Sync** — `lore sync` writes the top entries into your `MEMORY.md` so Claude Code surfaces them at session start.

Everything degrades gracefully without an API key — BM25 search still works, tags default to empty, and sync generates a plain-text summary.

---

## Installation

### Prerequisites

- Python 3.11+
- Git (optional, used to detect project name and record branch/hash)

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/JimJim12/lore.git
cd lore

# 2. Create a virtual environment
python3 -m venv venv

# 3. Install lore
venv/bin/pip install -e .
```

### Make `lore` available in your shell

Add an alias to your `~/.bashrc` or `~/.zshrc`:

```bash
alias lore="$HOME/lore/venv/bin/lore"
```

Or add the venv to your PATH:

```bash
export PATH="$HOME/lore/venv/bin:$PATH"
```

Reload your shell:

```bash
source ~/.bashrc   # or ~/.zshrc
```

---

## API key setup

`lore` uses Claude for tag extraction, query expansion, and re-ranking. Without a key it still works — search falls back to BM25 only.

Get a key at [console.anthropic.com](https://console.anthropic.com), then choose one of:

**Option 1 — `.env` file** (recommended for per-project keys):

```bash
cp .env.example .env
# edit .env and paste your key
```

```
ANTHROPIC_API_KEY=sk-ant-...
```

`lore` automatically loads `.env` from your project directory or any parent directory.

**Option 2 — shell export** (applies to all projects):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Add that line to your `~/.bashrc` or `~/.zshrc` to persist it across sessions.

---

## Usage

### Add a note

```bash
lore add "We chose PostgreSQL — relational data model with 12 foreign keys"

# Link to a file
lore add "JWT for auth — need stateless auth for mobile clients" --file src/auth/middleware.ts

# Add extra tags (Claude also extracts tags automatically)
lore add "Redis for caching — 10ms p99 target" --tag performance --tag infrastructure
```

### Search

```bash
# Semantic search (uses Claude if API key is set)
lore find "authentication decisions"

# Shorthand: frames the query as "why <topic>"
lore why "JWT"
lore why "PostgreSQL"
```

### Browse entries

```bash
# Recent entries table
lore list

# Filter by tag
lore list --tag auth
lore list --tag database

# Show a specific entry in full detail
lore show 3
```

### File links

```bash
# Link an existing entry to a file
lore link src/auth/middleware.ts 3 --note "Entry point for all auth checks"

# Show all notes linked to a file
lore files src/auth/middleware.ts
```

### Export

```bash
# Markdown to stdout
lore export

# Write to file
lore export --output DECISIONS.md
```

### Sync to MEMORY.md

`lore sync` writes the top entries (by importance score) into Claude Code's `MEMORY.md` for this project, so Claude surfaces them automatically at session start.

```bash
# Preview what would be written
lore sync --dry-run

# Write to MEMORY.md
lore sync

# Sync more entries (default: 10)
lore sync --top 20
```

### Delete

```bash
lore delete 3          # prompts for confirmation
lore delete 3 --yes    # skip confirmation
```

---

## Database

Each project gets its own database at `~/.lore/<project-name>.db`. The project name comes from the git repository root's directory name, falling back to the current directory name.

```
~/.lore/
├── my-app.db
├── my-api.db
└── frontend.db
```

---

## Graceful degradation

| Feature | With API key | Without API key |
|---|---|---|
| Tag extraction | Claude extracts tags + sets importance | Empty tags, importance defaults to 5 |
| Search | Query expansion + BM25 + re-ranking | BM25 with stop-word filtering |
| `lore sync` | Claude writes a concise summary | Bullet list of entry content |

---

## All commands

```
lore add       Add a new knowledge entry
lore find      Semantic search over all entries
lore why       Shorthand for find (frames as "why <topic>")
lore list      List recent entries (--tag to filter)
lore show      Show full detail for an entry
lore delete    Delete an entry (with confirmation)
lore link      Link a file path to an existing entry
lore files     Show all entries linked to a file
lore export    Export all entries as Markdown
lore sync      Sync top entries to MEMORY.md (--dry-run to preview)
```

Run `lore <command> --help` for options on any command.
