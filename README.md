# lore

Capture the *why* behind your code. `lore` stores architectural decisions and technical reasoning in a local SQLite database with full-text search, and uses Claude to make them semantically queryable.

Every project accumulates *why* knowledge — why PostgreSQL over MongoDB, why JWT over sessions, why this specific architecture. That reasoning lives in developers' heads and disappears between sessions. `lore` is a place to put it.

```
$ lore add "JWT for auth — need stateless auth for iOS and Android clients" \
    --file src/auth/middleware.ts

╭─────────────────────── Entry added ──────────────────────────╮
│ JWT for auth — need stateless auth for iOS and Android       │
│                                                              │
│ Tags: #authentication #JWT #mobile #iOS #Android            │
│ Category: security  Importance: ███████░░░ 7/10             │
│ ID: 4  Branch: main                                         │
╰──────────────────────────────────────────────────────────────╯

$ lore find "why did we pick JWT"

╭─── #1  95% relevance ────────────────────────────────────────╮
│ JWT for auth — need stateless auth for iOS and Android       │
│ Directly addresses stateless authentication for mobile       │
│                                                              │
│ Tags: #authentication #JWT #mobile  · security · 2026-03-01 │
╰──────────────────────────────────────────────────────────────╯
```

---

## How it works

When you add a note, Claude extracts tags, assigns an importance score (0–10), and picks a category. Notes are stored in a local SQLite database with an FTS5 full-text search index.

When you search, `lore` runs two passes:

1. **Recall** — Claude expands your query into synonyms and related terms, then runs a BM25 full-text search to pull up to 20 candidates.
2. **Re-rank** — Claude scores each candidate against your original query and returns a one-sentence reason per result.

`lore sync` selects the top entries by importance, asks Claude to write a concise summary, and writes it into Claude Code's `MEMORY.md` behind `<!-- lore:start -->...<!-- lore:end -->` markers. Claude Code loads this file at session start, so your architectural context is available immediately.

Everything degrades gracefully without an API key — full-text search still works, tags are left empty, and sync produces a plain bullet list.

---

## Installation

**Prerequisites:** Python 3.11+, Git (optional — used to detect project name and record the current branch and commit hash on each entry)

```bash
# Clone the repo
git clone https://github.com/JimJim12/lore.git
cd lore

# Create a virtual environment and install
python3 -m venv venv
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

Then reload:

```bash
source ~/.bashrc   # or ~/.zshrc
```

---

## API key setup

`lore` uses `claude-haiku` for tag extraction, query expansion, and re-ranking. Without a key it still works — search falls back to BM25 with stop-word filtering.

Get a key at [console.anthropic.com](https://console.anthropic.com), then choose one of:

**Option 1 — `.env` file** (recommended, keeps the key scoped to your environment):

```bash
cp .env.example .env
# open .env and paste your key
```

```
ANTHROPIC_API_KEY=sk-ant-...
```

`lore` automatically loads `.env` from the current directory or any parent, so you can place it at your home directory or project root and it will be picked up wherever you run `lore`.

**Option 2 — shell export** (applies globally across all shells):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Add that line to your `~/.bashrc` or `~/.zshrc` to persist it. A shell export takes precedence over `.env` if both are set.

---

## Usage

### Getting help

```bash
lore help                  # styled overview of all commands and options
lore <command> --help      # full flag details for a specific command
```

### Adding notes

The core workflow. Write in plain language — Claude handles the metadata.

```bash
lore add "We chose PostgreSQL — relational data with 12 foreign keys, need referential integrity"

# Link to one or more files
lore add "JWT for auth — stateless, works for iOS/Android" --file src/auth/middleware.ts

# --file can be repeated
lore add "Rate limiting at the nginx layer" \
    --file nginx/nginx.conf \
    --file src/middleware/rate-limit.ts

# Force extra tags on top of Claude's extracted ones
lore add "Redis for session cache — 10ms p99 target" --tag performance --tag infrastructure
```

### Searching

```bash
# Semantic search with Claude expansion and re-ranking
lore find "authentication decisions"
lore find "why are we using a message queue"
lore find "database performance tradeoffs"

# `why` is a shorthand that frames the query as "why <topic>"
lore why "JWT"
lore why "PostgreSQL"
lore why "Redis"
```

### Browsing entries

```bash
# Recent entries as a table (default 20)
lore list

# Filter by tag
lore list --tag auth
lore list --tag database

# Change the limit
lore list --limit 50

# Full detail for one entry, including file links and git info
lore show 4
```

### Linking files

Files can be linked at add-time with `--file`, or linked later to an existing entry:

```bash
# Link a file to entry #4 after the fact
lore link src/auth/middleware.ts 4 --note "Entry point for all auth checks"

# See all notes associated with a file
lore files src/auth/middleware.ts
```

This is useful for answering "why does this file exist / work this way?" directly from the filename.

### Exporting

```bash
# Dump everything as Markdown to stdout
lore export

# Write to a file — useful for committing decisions alongside code
lore export --output DECISIONS.md
```

### Syncing to MEMORY.md

`lore sync` writes the top-N entries (ranked by importance) into Claude Code's `MEMORY.md` for the current project. Claude Code loads this file at the start of every session, so your architectural decisions are available to Claude without any manual copy-paste.

```bash
# Preview the section that would be written
lore sync --dry-run

# Write it (replaces any existing lore block)
lore sync

# Include more entries
lore sync --top 20
```

The written block is wrapped in `<!-- lore:start -->...<!-- lore:end -->` markers, so running `lore sync` again safely replaces the previous block without touching anything else in the file.

### Deleting

```bash
lore delete 4            # shows the entry and prompts for confirmation
lore delete 4 --yes      # skip the prompt
```

---

## Database

Each project gets its own database at `~/.lore/<project-name>.db`. The project name is taken from the git repository root's directory name, falling back to the current directory name if you're not in a git repo.

```
~/.lore/
├── my-app.db
├── my-api.db
└── frontend.db
```

The schema uses an [FTS5](https://www.sqlite.org/fts5.html) virtual table with porter stemming over the note content and tags, kept in sync with the main `entries` table via triggers. Searches use BM25 ranking.

---

## Graceful degradation

All Claude API calls return `None` on any failure — missing key, network error, malformed response — and every caller has a non-Claude fallback. Nothing crashes without an API key.

| Feature | With API key | Without API key |
|---|---|---|
| Tag extraction | Claude extracts tags, importance, category | Empty tags, importance defaults to 5, category to `other` |
| Search | Query expansion + BM25 recall + Claude re-ranking | BM25 with stop-word filtering and prefix matching |
| `lore sync` | Claude writes a structured, grouped summary | Plain bullet list of entry content |

---

## Command reference

| Command | Arguments | Options |
|---|---|---|
| `add` | `<note>` | `--file/-f`, `--tag/-t` |
| `find` | `<query>` | — |
| `why` | `<topic>` | — |
| `list` | — | `--tag/-t`, `--limit/-n` |
| `show` | `<id>` | — |
| `delete` | `<id>` | `--yes/-y` |
| `link` | `<file> <id>` | `--note/-n` |
| `files` | `<file>` | — |
| `export` | — | `--output/-o` |
| `sync` | — | `--dry-run`, `--top` |
| `help` | — | — |
