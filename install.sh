#!/bin/bash
# Valor installer -- deploys agent rule + commands to Claude Code, Codex, and Cursor.
#
# Source of truth: rules/valor-agent.md + commands/*.md (Claude Code format)
# For Cursor/Codex: install.sh generates SKILL.md wrappers with frontmatter.
#
# Usage:
#   ./install.sh                              Install for all targets (default)
#   ./install.sh --target all                 Same as above
#   ./install.sh --target claude-code         Install for Claude Code only
#   ./install.sh --target codex               Install for Codex CLI only
#   ./install.sh --target cursor              Install for Cursor only
#   ./install.sh --check                      Check for drift (uses current target)
#   ./install.sh --target codex --check       Check drift for Codex
#   ./install.sh --version                    Print version and exit
#   ./install.sh --upgrade                    Pull latest + re-install
#   ./install.sh --auto-update                Pull latest + quiet re-install (for agent-triggered updates)
#
# Quick install (clones repo then installs):
#   curl -fsSL https://raw.githubusercontent.com/yihanzhu/valor/main/install.sh | bash -s -- --clone

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VALOR_HOME="$HOME/.valor"
VALOR_REPO="https://github.com/yihanzhu/valor.git"
VALOR_CLONE_DIR="$VALOR_HOME/repo"

# --- Handle --clone early (bootstrap from remote) ---
for arg in "$@"; do
    if [ "$arg" = "--clone" ]; then
        mkdir -p "$VALOR_HOME"
        # Migrate from legacy ~/valor to ~/.valor/repo/ if needed
        if [ -d "$HOME/valor/.git" ] && [ ! -d "$VALOR_CLONE_DIR/.git" ]; then
            echo "Migrating Valor repo from ~/valor to $VALOR_CLONE_DIR..."
            mv "$HOME/valor" "$VALOR_CLONE_DIR"
        fi
        if [ -d "$VALOR_CLONE_DIR/.git" ]; then
            echo "Valor repo already exists at $VALOR_CLONE_DIR -- pulling latest..."
            git -C "$VALOR_CLONE_DIR" pull --ff-only
        else
            echo "Cloning Valor to $VALOR_CLONE_DIR..."
            git clone "$VALOR_REPO" "$VALOR_CLONE_DIR"
        fi
        remaining_args=()
        for a in "$@"; do
            [ "$a" != "--clone" ] && remaining_args+=("$a")
        done
        exec bash "$VALOR_CLONE_DIR/install.sh" "${remaining_args[@]+"${remaining_args[@]}"}"
    fi
done

# --- Command source files and their target names ---
# Format: "source-name:claude-code-name:cursor-skill-name:cursor-description"
# source-name: filename in commands/ (without .md), also the plugin command name
# claude-code-name: filename when installed standalone to ~/.claude/commands/
COMMAND_MAP=(
    "briefing:valor-briefing:valor-morning-briefing:Valor morning briefing: gathers Jira tickets, PRs, calendar, tech/world news, and career coaching into a comprehensive daily briefing"
    "pr-review:valor-pr-review:valor-pr-review-coach:Valor PR review coach: helps give senior-level code review feedback with architecture, testing, and career coaching annotations"
    "design-doc:valor-design-doc:valor-design-doc-coach:Valor design doc coach: helps write technical design documents with structured options, trade-offs, and career coaching"
    "weekly:valor-weekly:valor-weekly-reflection:Valor weekly reflection: summarizes the week's work mapped to target-level competencies, identifies gaps, generates narrative for 1:1 with manager"
    "tasks:valor-tasks:valor-task-identifier:Valor task identifier: finds high-impact work opportunities prioritized by career growth potential and team need"
    "wrapup:valor-wrapup:valor-evening-wrapup:Valor evening wrap-up: summarizes the day's work, captures carry-forward items for tomorrow, and reflects on competencies exercised"
    "prep:valor-prep:valor-prep:Valor 1:1 prep: generates a structured document for manager 1:1s grounded in evidence, weekly summaries, and career framework alignment"
    "setup:valor-setup:valor-setup:Valor setup: guided configuration of career framework, levels, and integrations"
)

# --- Version ---
VALOR_VERSION="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo "unknown")"

# --- Parse arguments ---
TARGET="all"
CHECK_ONLY=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --target)
            shift
            if [ "$#" -eq 0 ]; then
                echo "Missing value for --target (use 'claude-code', 'codex', 'cursor', or 'all')"
                exit 1
            fi
            TARGET="$1"
            ;;
        --check)
            CHECK_ONLY=true
            ;;
        --version)
            echo "Valor $VALOR_VERSION"
            exit 0
            ;;
        --upgrade)
            echo "=== Valor Upgrade ==="
            echo ""
            if [ -d "$SCRIPT_DIR/.git" ]; then
                echo "Pulling latest from $(git -C "$SCRIPT_DIR" remote get-url origin 2>/dev/null || echo 'origin')..."
                git -C "$SCRIPT_DIR" pull --ff-only || {
                    echo "Pull failed. Resolve conflicts manually, then re-run install.sh."
                    exit 1
                }
                VALOR_VERSION="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo "unknown")"
                echo "[OK] Updated to Valor $VALOR_VERSION"
                echo ""
            else
                echo "Not a git repo -- cannot auto-upgrade. Run 'git pull' manually."
                exit 1
            fi
            ;;
        --auto-update)
            old_version="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo "unknown")"
            repo_dir="$VALOR_HOME/repo"
            if [ -d "$repo_dir/.git" ]; then
                git -C "$repo_dir" pull --ff-only >/dev/null 2>&1 || {
                    echo "Valor auto-update: pull failed (offline?)" >&2
                    exit 1
                }
                new_version="$(cat "$repo_dir/VERSION" 2>/dev/null || echo "unknown")"
                if [ "$old_version" = "$new_version" ]; then
                    echo "Valor is already up to date ($new_version)."
                    exit 0
                fi
                bash "$repo_dir/install.sh" --target all >/dev/null 2>&1
                echo "Valor updated: $old_version -> $new_version"
            else
                echo "Valor auto-update: no repo at $repo_dir (run install.sh --clone first)" >&2
                exit 1
            fi
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
    shift
done

# --- Handle --target all by re-invoking for each target ---
if [ "$TARGET" = "all" ]; then
    overall_exit=0
    check_flag=""
    [ "$CHECK_ONLY" = true ] && check_flag="--check"
    for t in claude-code codex cursor; do
        echo ""
        bash "$SCRIPT_DIR/install.sh" --target "$t" $check_flag || overall_exit=$?
        echo ""
    done
    exit "$overall_exit"
fi

# --- Target-specific paths ---
if [ "$TARGET" = "cursor" ]; then
    AGENT_RULES="$HOME/.cursor/rules"
    AGENT_SKILLS="$HOME/.cursor/skills"
elif [ "$TARGET" = "codex" ]; then
    CODEX_DIR="$HOME/.codex"
    CODEX_SKILLS="$CODEX_DIR/skills"
elif [ "$TARGET" = "claude-code" ]; then
    CLAUDE_DIR="$HOME/.claude"
    CLAUDE_COMMANDS="$CLAUDE_DIR/commands"
else
    echo "Unknown target: $TARGET (use 'claude-code', 'codex', or 'cursor')"
    exit 1
fi

RULE_SOURCE="$SCRIPT_DIR/rules/valor-agent.md"

# --- Auto-detect available integrations ---
# Only GitHub can be detected (gh CLI + auth). Jira, calendar, and news
# default to true -- the user can disable them in state.json.
detect_integrations() {
    local github="false"
    if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
        github="true"
    fi
    echo "{\"github\": $github, \"jira\": true, \"calendar\": true, \"news\": true}"
}

# --- Shared sed transforms for non-Claude-Code targets (stdin -> stdout) ---
# Adding a new command? Update COMMAND_MAP above and add one line here.
apply_shared_transforms() {
    sed \
        -e 's|/valor-briefing|valor-morning-briefing skill|g' \
        -e 's|/valor-pr-review|valor-pr-review-coach skill|g' \
        -e 's|/valor-design-doc|valor-design-doc-coach skill|g' \
        -e 's|/valor-weekly|valor-weekly-reflection skill|g' \
        -e 's|/valor-tasks|valor-task-identifier skill|g' \
        -e 's|/valor-wrapup|valor-evening-wrapup skill|g' \
        -e 's|/valor-prep|valor-prep skill|g' \
        -e 's|/valor-setup|valor-setup skill|g' \
        -e 's|Bash tool|Shell tool|g'
}

# --- Backtick command references -> skill paths for a target dir (stdin -> stdout) ---
# Run BEFORE apply_shared_transforms so the more specific patterns match first.
apply_rule_transforms() {
    local target_dir="$1"
    sed \
        -e "s|\`/valor-briefing\` command|\`~/$target_dir/skills/valor-morning-briefing/SKILL.md\`|g" \
        -e "s|\`/valor-pr-review\` command|\`~/$target_dir/skills/valor-pr-review-coach/SKILL.md\`|g" \
        -e "s|\`/valor-design-doc\` command|\`~/$target_dir/skills/valor-design-doc-coach/SKILL.md\`|g" \
        -e "s|\`/valor-weekly\` command|\`~/$target_dir/skills/valor-weekly-reflection/SKILL.md\`|g" \
        -e "s|\`/valor-tasks\` command|\`~/$target_dir/skills/valor-task-identifier/SKILL.md\`|g" \
        -e "s|\`/valor-wrapup\` command|\`~/$target_dir/skills/valor-evening-wrapup/SKILL.md\`|g" \
        -e "s|\`/valor-prep\` command|\`~/$target_dir/skills/valor-prep/SKILL.md\`|g" \
        -e "s|\`/valor-setup\` command|\`~/$target_dir/skills/valor-setup/SKILL.md\`|g"
}

# --- Generate Cursor .mdc from the universal agent rule ---
generate_cursor_rule() {
    local src="$1"
    local dst="$2"
    {
        echo '---'
        echo 'description: "Valor (Versatile Assistant for Life, Organization, and Reasoning) -- career growth assistant with contextual coaching agents"'
        echo 'alwaysApply: true'
        echo '---'
        echo ""
        apply_rule_transforms ".cursor" < "$src" | apply_shared_transforms
    } > "$dst"
}

# --- Generate Codex AGENTS.md content from the universal agent rule (stdout) ---
generate_codex_rule_content() {
    local src="$1"
    apply_rule_transforms ".codex" < "$src" | apply_shared_transforms
}

# --- Generate SKILL.md from a command file (shared by Cursor and Codex) ---
generate_skill() {
    local src="$1"
    local dst="$2"
    local skill_name="$3"
    local description="$4"
    {
        echo '---'
        echo "name: $skill_name"
        echo "description: \"$description\""
        echo '---'
        echo ""
        apply_shared_transforms < "$src"
    } > "$dst"
}

# --- Drift check ---
check_drift() {
    local drift_count=0

    # Check runtime files
    local runtime_sources=(
        "$SCRIPT_DIR/src/evidence_cli.py"
        "$SCRIPT_DIR/src/career_framework.md"
        "$SCRIPT_DIR/src/utilities.md"
    )
    local runtime_dests=(
        "$VALOR_HOME/evidence_cli.py"
        "$VALOR_HOME/career_framework.md"
        "$VALOR_HOME/utilities.md"
    )

    for i in "${!runtime_sources[@]}"; do
        local src="${runtime_sources[$i]}"
        local dst="${runtime_dests[$i]}"
        if [ ! -f "$dst" ]; then
            echo "[MISSING] $dst"
            drift_count=$((drift_count + 1))
        elif ! diff -q "$src" "$dst" > /dev/null 2>&1; then
            echo "[DRIFT]   $dst"
            drift_count=$((drift_count + 1))
        else
            echo "[OK]      $dst"
        fi
    done

    # Check agent rule
    if [ "$TARGET" = "claude-code" ]; then
        local marker_start="# --- BEGIN VALOR ---"
        local marker_end="# --- END VALOR ---"
        local rule_dest="$CLAUDE_DIR/CLAUDE.md"
        if [ ! -f "$rule_dest" ]; then
            echo "[MISSING] $rule_dest"
            drift_count=$((drift_count + 1))
        elif grep -q "$marker_start" "$rule_dest" 2>/dev/null; then
            local tmp_extracted
            tmp_extracted=$(mktemp)
            sed -n "/$marker_start/,/$marker_end/{
                /$marker_start/d
                /$marker_end/d
                p
            }" "$rule_dest" > "$tmp_extracted"
            if ! diff -q "$RULE_SOURCE" "$tmp_extracted" > /dev/null 2>&1; then
                echo "[DRIFT]   $rule_dest (valor section)"
                drift_count=$((drift_count + 1))
            else
                echo "[OK]      $rule_dest (valor section)"
            fi
            rm -f "$tmp_extracted"
        else
            echo "[MISSING] $rule_dest (no valor section)"
            drift_count=$((drift_count + 1))
        fi
    elif [ "$TARGET" = "codex" ]; then
        local rule_dest="$CODEX_DIR/AGENTS.md"
        local marker_start="# --- BEGIN VALOR ---"
        local marker_end="# --- END VALOR ---"
        if [ ! -f "$rule_dest" ]; then
            echo "[MISSING] $rule_dest"
            drift_count=$((drift_count + 1))
        elif grep -q "$marker_start" "$rule_dest" 2>/dev/null; then
            local tmp_extracted
            tmp_extracted=$(mktemp)
            sed -n "/$marker_start/,/$marker_end/{
                /$marker_start/d
                /$marker_end/d
                p
            }" "$rule_dest" > "$tmp_extracted"
            local tmp_expected
            tmp_expected=$(mktemp)
            generate_codex_rule_content "$RULE_SOURCE" > "$tmp_expected"
            if ! diff -q "$tmp_expected" "$tmp_extracted" > /dev/null 2>&1; then
                echo "[DRIFT]   $rule_dest (valor section)"
                drift_count=$((drift_count + 1))
            else
                echo "[OK]      $rule_dest (valor section)"
            fi
            rm -f "$tmp_extracted" "$tmp_expected"
        else
            echo "[MISSING] $rule_dest (no valor section)"
            drift_count=$((drift_count + 1))
        fi
    elif [ "$TARGET" = "cursor" ]; then
        local rule_dest="$AGENT_RULES/valor-agent.mdc"
        if [ ! -f "$rule_dest" ]; then
            echo "[MISSING] $rule_dest"
            drift_count=$((drift_count + 1))
        else
            local tmp_generated
            tmp_generated=$(mktemp)
            generate_cursor_rule "$RULE_SOURCE" "$tmp_generated"
            if ! diff -q "$tmp_generated" "$rule_dest" > /dev/null 2>&1; then
                echo "[DRIFT]   $rule_dest"
                drift_count=$((drift_count + 1))
            else
                echo "[OK]      $rule_dest"
            fi
            rm -f "$tmp_generated"
        fi
    fi

    # Check commands/skills
    for entry in "${COMMAND_MAP[@]}"; do
        IFS=':' read -r src_name cc_name skill_name description <<< "$entry"
        local src="$SCRIPT_DIR/commands/$src_name.md"

        if [ ! -f "$src" ]; then
            echo "[MISSING SRC] $src"
            drift_count=$((drift_count + 1))
            continue
        fi

        if [ "$TARGET" = "claude-code" ]; then
            local dst="$CLAUDE_COMMANDS/$cc_name.md"
            if [ ! -f "$dst" ]; then
                echo "[MISSING] $dst"
                drift_count=$((drift_count + 1))
            elif ! diff -q "$src" "$dst" > /dev/null 2>&1; then
                echo "[DRIFT]   $dst"
                drift_count=$((drift_count + 1))
            else
                echo "[OK]      $dst"
            fi
        else
            # Codex and Cursor both use generated SKILL.md wrappers
            local skills_root=""
            [ "$TARGET" = "codex" ] && skills_root="$CODEX_SKILLS"
            [ "$TARGET" = "cursor" ] && skills_root="$AGENT_SKILLS"
            local dst="$skills_root/$skill_name/SKILL.md"
            if [ ! -f "$dst" ]; then
                echo "[MISSING] $dst"
                drift_count=$((drift_count + 1))
            else
                local tmp_generated
                tmp_generated=$(mktemp)
                generate_skill "$src" "$tmp_generated" "$skill_name" "$description"
                if ! diff -q "$tmp_generated" "$dst" > /dev/null 2>&1; then
                    echo "[DRIFT]   $dst"
                    drift_count=$((drift_count + 1))
                else
                    echo "[OK]      $dst"
                fi
                rm -f "$tmp_generated"
            fi
        fi
    done

    echo ""
    if [ "$drift_count" -eq 0 ]; then
        echo "All installed files match the repo source ($TARGET)."
    else
        echo "$drift_count file(s) out of sync. Run ./install.sh --target $TARGET to update."
    fi
    return "$drift_count"
}

if [ "$CHECK_ONLY" = true ]; then
    echo "=== Valor Drift Check ($TARGET) ==="
    echo ""
    check_drift
    exit $?
fi

echo "=== Valor Installer ($TARGET) ==="
echo ""

# 1. Create ~/.valor/ for state and evidence storage
mkdir -p "$VALOR_HOME"
mkdir -p "$VALOR_HOME/carry-forward"

DETECTED_INTEGRATIONS=$(detect_integrations)

STATE_SCHEMA_VERSION=3

if [ ! -f "$VALOR_HOME/state.json" ]; then
    cat > "$VALOR_HOME/state.json" <<STATEJSON
{
  "state_schema_version": $STATE_SCHEMA_VERSION,
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
  "integrations": $DETECTED_INTEGRATIONS,
  "last_update_check": "",
  "update_check_interval_hours": 24
}
STATEJSON
    echo "[OK] Created $VALOR_HOME/state.json (integrations auto-detected)"
    echo "     ⚠️  Edit this file to set current_level, target_level, ceiling_level,"
    echo "        github_owner, and jira_projects for your setup."
else
    # Migrate state.json to current schema
    python3 -c "
import json, sys
state = json.loads(open(sys.argv[1]).read())
target_version = int(sys.argv[2])
current_version = state.get('state_schema_version', 1)
changed = False
# v1 -> v2: add integrations and state_schema_version
if current_version < 2:
    if 'integrations' not in state:
        state['integrations'] = json.loads(sys.argv[3])
        changed = True
    if 'state_schema_version' not in state:
        changed = True
# v2 -> v3: add auto-update fields
if current_version < 3:
    if 'last_update_check' not in state:
        state['last_update_check'] = ''
        changed = True
    if 'update_check_interval_hours' not in state:
        state['update_check_interval_hours'] = 24
        changed = True
if state.get('state_schema_version', 1) < target_version:
    state['state_schema_version'] = target_version
    changed = True
if changed:
    open(sys.argv[1], 'w').write(json.dumps(state, indent=2))
    print(f'[OK] state.json migrated to schema v{target_version}')
else:
    print('[OK] state.json already up to date')
" "$VALOR_HOME/state.json" "$STATE_SCHEMA_VERSION" "$DETECTED_INTEGRATIONS"
fi

# 2. Copy evidence CLI and career framework to ~/.valor/
cp "$SCRIPT_DIR/src/evidence_cli.py" "$VALOR_HOME/evidence_cli.py"
echo "[OK] Installed evidence CLI -> $VALOR_HOME/evidence_cli.py"
if [ ! -f "$VALOR_HOME/career_framework.md" ]; then
    cp "$SCRIPT_DIR/src/career_framework.md" "$VALOR_HOME/career_framework.md"
    echo "[OK] Installed career framework template -> $VALOR_HOME/career_framework.md"
    echo "     ⚠️  Edit this file with your company's levels, competencies, and values."
else
    echo "[OK] Career framework exists (not overwritten) -> $VALOR_HOME/career_framework.md"
fi
cp "$SCRIPT_DIR/src/utilities.md" "$VALOR_HOME/utilities.md"
echo "[OK] Installed utilities reference -> $VALOR_HOME/utilities.md"

# 3. Install agent-specific files
if [ "$TARGET" = "cursor" ]; then
    mkdir -p "$AGENT_RULES"
    generate_cursor_rule "$RULE_SOURCE" "$AGENT_RULES/valor-agent.mdc"
    echo "[OK] Generated rule -> $AGENT_RULES/valor-agent.mdc"

elif [ "$TARGET" = "codex" ]; then
    mkdir -p "$CODEX_DIR"

    MARKER_START="# --- BEGIN VALOR ---"
    MARKER_END="# --- END VALOR ---"

    if [ -f "$CODEX_DIR/AGENTS.md" ]; then
        if grep -q "$MARKER_START" "$CODEX_DIR/AGENTS.md" 2>/dev/null; then
            tmp_file=$(mktemp)
            sed "/$MARKER_START/,/$MARKER_END/d" "$CODEX_DIR/AGENTS.md" > "$tmp_file"
            mv "$tmp_file" "$CODEX_DIR/AGENTS.md"
            echo "[OK] Removed old Valor section from AGENTS.md"
        fi
    fi

    {
        echo ""
        echo "$MARKER_START"
        generate_codex_rule_content "$RULE_SOURCE"
        echo "$MARKER_END"
    } >> "$CODEX_DIR/AGENTS.md"
    echo "[OK] Installed Valor agent rule -> $CODEX_DIR/AGENTS.md (appended)"

elif [ "$TARGET" = "claude-code" ]; then
    mkdir -p "$CLAUDE_DIR"
    mkdir -p "$CLAUDE_COMMANDS"

    MARKER_START="# --- BEGIN VALOR ---"
    MARKER_END="# --- END VALOR ---"

    if [ -f "$CLAUDE_DIR/CLAUDE.md" ]; then
        if grep -q "$MARKER_START" "$CLAUDE_DIR/CLAUDE.md" 2>/dev/null; then
            tmp_file=$(mktemp)
            sed "/$MARKER_START/,/$MARKER_END/d" "$CLAUDE_DIR/CLAUDE.md" > "$tmp_file"
            mv "$tmp_file" "$CLAUDE_DIR/CLAUDE.md"
            echo "[OK] Removed old Valor section from CLAUDE.md"
        fi
    fi

    {
        echo ""
        echo "$MARKER_START"
        cat "$RULE_SOURCE"
        echo "$MARKER_END"
    } >> "$CLAUDE_DIR/CLAUDE.md"
    echo "[OK] Installed Valor agent rule -> $CLAUDE_DIR/CLAUDE.md (appended)"

    for entry in "${COMMAND_MAP[@]}"; do
        IFS=':' read -r src_name cc_name skill_name description <<< "$entry"
        cp "$SCRIPT_DIR/commands/$src_name.md" "$CLAUDE_COMMANDS/$cc_name.md"
        echo "[OK] Installed command -> $CLAUDE_COMMANDS/$cc_name.md"
    done

fi

# Install skills (Codex and Cursor share the same generate_skill pipeline)
if [ "$TARGET" = "codex" ] || [ "$TARGET" = "cursor" ]; then
    SKILLS_ROOT=""
    [ "$TARGET" = "codex" ] && SKILLS_ROOT="$CODEX_SKILLS"
    [ "$TARGET" = "cursor" ] && SKILLS_ROOT="$AGENT_SKILLS"

    for entry in "${COMMAND_MAP[@]}"; do
        IFS=':' read -r src_name cc_name skill_name description <<< "$entry"
        mkdir -p "$SKILLS_ROOT/$skill_name"
        generate_skill "$SCRIPT_DIR/commands/$src_name.md" \
            "$SKILLS_ROOT/$skill_name/SKILL.md" "$skill_name" "$description"
        echo "[OK] Generated skill -> $SKILLS_ROOT/$skill_name/"
    done
fi

# 4. Record installed version
python3 -c "
import json
from datetime import datetime
from pathlib import Path
p = Path.home() / '.valor' / 'state.json'
if p.exists():
    state = json.loads(p.read_text())
    state['installed_version'] = '$VALOR_VERSION'
    state['installed_at'] = datetime.now().isoformat(timespec='seconds')
    p.write_text(json.dumps(state, indent=2))
" 2>/dev/null

# 5. Post-install verification
echo ""
echo "=== Post-Install Verification ==="
echo ""
if check_drift; then
    echo ""
    echo "=== Installation Complete ($TARGET) ==="
else
    echo ""
    echo "=== Installation Complete (with warnings) ==="
fi

echo ""
if [ "$TARGET" = "claude-code" ]; then
    echo "Valor agents installed for Claude Code:"
    echo "  1. Morning Briefing   -- auto-suggests before 11am, or /valor-briefing"
    echo "  2. PR Review Coach    -- /valor-pr-review"
    echo "  3. Design Doc Coach   -- /valor-design-doc"
    echo "  4. Weekly Reflection   -- auto-suggests Friday, or /valor-weekly"
    echo "  5. Task Identifier    -- /valor-tasks"
    echo "  6. Evening Wrap-up   -- auto-suggests after 5pm, or /valor-wrapup"
    echo "  7. 1:1 Prep           -- /valor-prep"
    echo "  8. Setup              -- /valor-setup (run this first!)"
    echo "  9. Ambient Coaching   -- always on (say 'valor quiet' to suppress)"
elif [ "$TARGET" = "codex" ]; then
    echo "Valor agents installed for Codex CLI:"
    echo "  1. Morning Briefing   -- auto-suggests before 11am, or say 'morning briefing'"
    echo "  2. PR Review Coach    -- say 'review PR #NNN' or 'help me review'"
    echo "  3. Design Doc Coach   -- say 'design doc for TICKET' or 'how should I approach'"
    echo "  4. Weekly Reflection   -- auto-suggests Friday, or say 'weekly reflection'"
    echo "  5. Task Identifier    -- say 'what should I work on' or 'find me work'"
    echo "  6. Evening Wrap-up   -- auto-suggests after 5pm, or say 'wrap up'"
    echo "  7. 1:1 Prep           -- say 'prep for 1:1' or '1:1 prep'"
    echo "  8. Setup              -- say 'set up valor' (run this first!)"
    echo "  9. Ambient Coaching   -- always on (say 'valor quiet' to suppress)"
    echo ""
    echo "Agent rule: $CODEX_DIR/AGENTS.md"
    echo "Skills:     $CODEX_SKILLS/valor-*/"
else
    echo "Valor agents installed for Cursor:"
    echo "  1. Morning Briefing   -- auto-suggests before 11am, or say 'morning briefing'"
    echo "  2. PR Review Coach    -- say 'review PR #NNN' or 'help me review'"
    echo "  3. Design Doc Coach   -- say 'design doc for TICKET' or 'how should I approach'"
    echo "  4. Weekly Reflection   -- auto-suggests Friday, or say 'weekly reflection'"
    echo "  5. Task Identifier    -- say 'what should I work on' or 'find me work'"
    echo "  6. Evening Wrap-up   -- auto-suggests after 5pm, or say 'wrap up'"
    echo "  7. 1:1 Prep           -- say 'prep for 1:1' or '1:1 prep'"
    echo "  8. Setup              -- say 'set up valor' (run this first!)"
    echo "  9. Ambient Coaching   -- always on (say 'valor quiet' to suppress)"
fi
echo ""
if [ "$TARGET" = "claude-code" ]; then
    echo "Next step: open your agent and run /valor-setup to configure your"
    echo "           career framework, levels, and integrations."
else
    echo "Next step: open your agent and say 'set up valor' to configure your"
    echo "           career framework, levels, and integrations."
fi
echo ""
if [ "$TARGET" = "claude-code" ]; then
    echo "Integrations (auto-detected, reconfigure via /valor-setup):"
else
    echo "Integrations (auto-detected, reconfigure by saying 'set up valor'):"
fi
# Parse detected integrations for display
python3 -c "
import json
from pathlib import Path
state = json.loads((Path.home() / '.valor' / 'state.json').read_text())
intg = state.get('integrations', {})
labels = {'github': 'GitHub (gh CLI)', 'jira': 'Jira/Atlassian', 'calendar': 'Google Calendar', 'news': 'Web news'}
for key, label in labels.items():
    status = 'enabled' if intg.get(key, False) else 'disabled'
    icon = '✓' if intg.get(key, False) else '✗'
    print(f'  {icon} {label}: {status}')
" 2>/dev/null || echo "  (could not read integrations from state.json)"
echo ""
echo "State & evidence stored at: $VALOR_HOME/"
echo "Evidence CLI: python3 $VALOR_HOME/evidence_cli.py stats"
echo ""
echo "Tip: Run './install.sh --target $TARGET --check' anytime to verify installed files match the repo."
