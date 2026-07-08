---
name: setup
description: "Initialize Valor local state (~/.valor/) for first-time users. Run this after installing the plugin."
---

# Valor Setup

Initialize the local Valor directory at `~/.valor/` for first-time use.

> **Plugin-only path — limited by design.** This skill seeds local state and
> copies a *limited* helper set so the core commands can run. It does **not**
> install every shared helper, and it cannot enable ambient coaching. For the
> full experience, run `install.sh` from the Valor repo (see step 7).

## Steps

### 1. Check if already initialized

```bash
ls -la ~/.valor/state.json 2>/dev/null
```

If `state.json` exists, tell the user: "Valor is already set up. Your state
and evidence are at `~/.valor/`. Run `valor-evidence stats` to see your
evidence summary."

### 2. Create the directory

```bash
mkdir -p ~/.valor/carry-forward
```

### 3. Install the evidence CLI

The evidence CLI is bundled with the plugin at `bin/valor-evidence`, but it
needs the Python script at `~/.valor/evidence_cli.py`. Find the plugin
directory and copy it:

```bash
# The plugin's bin/ directory is on PATH when the plugin is enabled.
# The evidence_cli.py source is next to the bin/ directory in the plugin.
PLUGIN_DIR="$(dirname "$(dirname "$(which valor-evidence)")")"
cp "$PLUGIN_DIR/src/evidence_cli.py" ~/.valor/evidence_cli.py
```

If that fails, tell the user to run `install.sh` from the Valor repo
instead.

### 4. Seed `state.json` via the CLI

Let the CLI create and seed `state.json`. It owns the schema
(`STATE_SCHEMA_VERSION` in `evidence_cli.py`) and writes the current version
with all default fields, so this never pins a stale schema literal:

```bash
python3 ~/.valor/evidence_cli.py state-migrate
```

Do **not** hand-write `state.json` or a `state_schema_version` number here —
the CLI is the single source of truth for the schema, and duplicating it is
exactly how the two drifted apart.

### 5. Install the career framework template

```bash
cp "$PLUGIN_DIR/src/career_framework.md" ~/.valor/career_framework.md
cp "$PLUGIN_DIR/src/utilities.md" ~/.valor/utilities.md
```

### 6. Detect GitHub CLI

```bash
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    python3 -c "
import json
from pathlib import Path
p = Path.home() / '.valor' / 'state.json'
state = json.loads(p.read_text())
state['integrations']['github'] = True
p.write_text(json.dumps(state, indent=2))
"
    echo "GitHub CLI detected and authenticated."
fi
```

### 7. Configure your framework and levels via `/valor-setup`

Do **not** walk the user through editing `career_framework.md` or setting
levels here — that logic lives in one place, the `/valor-setup` command.
Hand off to it:

> Run `/valor-setup` (or say "set up valor") to fill in your career framework
> (levels, competencies, values), set your current / target / ceiling levels,
> and configure integrations and routines. It is re-runnable and only walks
> through what is still missing.

### 8. Full experience: run `install.sh`

The plugin-only path above installs a **limited** helper set —
`evidence_cli.py`, `career_framework.md`, and `utilities.md`. It does not copy
the other shared helpers, so features that depend on them are unavailable
until you run `install.sh`:

- **`verify.py`** — the verification gate used by `/valor-briefing` and
  `/valor-wrapup`.
- **`plan.py`** — day-planning / calendar fit used by `/valor-briefing`.
- **`focus.py`** — project-focus planning.
- **`collect_transcripts.py`** — the local coverage check in
  `/valor-reflection`.

Ambient coaching (always-on career coaching after tasks) also requires adding
Valor's rule to your `~/.claude/CLAUDE.md`, which the plugin cannot do. Run
`install.sh` from the Valor repo to copy the full helper set and enable
ambient coaching:

```bash
cd ~/.valor/repo && bash install.sh
```

Without `install.sh`, the command set still loads, but the features listed
above and automatic coaching annotations after tasks are not available.
