---
name: setup
description: "Initialize Valor local state (~/.valor/) for first-time users. Run this after installing the plugin."
---

# Valor Setup

Initialize the local Valor directory at `~/.valor/` for first-time use.

## Steps

### 1. Check if already initialized

```bash
ls -la ~/.valor/state.json 2>/dev/null
```

If `state.json` exists, tell the user: "Valor is already set up. Your state
and evidence are at `~/.valor/`. Run `valor-evidence stats` to see your
evidence summary."

### 2. Create the directory and state file

```bash
mkdir -p ~/.valor/carry-forward
```

Create `~/.valor/state.json` with initial content:

```bash
cat > ~/.valor/state.json <<'JSON'
{
  "state_schema_version": 2,
  "current_level": "",
  "target_level": "",
  "ceiling_level": "",
  "last_briefing_date": "",
  "last_briefing_timestamp": "",
  "briefing_count": 0,
  "coaching_mode": "ambient",
  "user_work_areas": [],
  "user_work_areas_pinned": [],
  "github_owner": "",
  "jira_projects": [],
  "integrations": {
    "github": false,
    "jira": false,
    "calendar": false,
    "news": true
  }
}
JSON
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

### 4. Install the career framework template

```bash
cp "$PLUGIN_DIR/src/career_framework.md" ~/.valor/career_framework.md
cp "$PLUGIN_DIR/src/utilities.md" ~/.valor/utilities.md
```

### 5. Detect GitHub CLI

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

### 6. Guide the user

Tell the user:

1. **Edit your career framework:** `~/.valor/career_framework.md` -- fill in
   your company's levels, competencies, and values.
2. **Set your levels:** Edit `~/.valor/state.json` and set `current_level`,
   `target_level`, and `ceiling_level` (e.g., "L3", "L4", "L5").
3. **Configure integrations:** Set `github_owner` and `jira_projects` in
   state.json if applicable. Set integration flags to `true` for tools you
   have available.

### 7. Note about ambient coaching

The ambient coaching rule (always-on career coaching after tasks) requires
adding Valor's rule to your `~/.claude/CLAUDE.md`. This is not handled by
the plugin -- run `install.sh` from the Valor repo for ambient coaching:

```bash
cd ~/valor && bash install.sh
```

Without this step, the 7 Valor commands (`/valor:briefing`,
`/valor:weekly`, `/valor:prep`, etc.) work normally, but you won't get
automatic coaching annotations after tasks.
