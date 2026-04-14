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

RULE_SOURCE="$SCRIPT_DIR/rules/valor-agent.md"

# --- Handle --target all --check by re-invoking per target (detailed output) ---
if [ "$TARGET" = "all" ] && [ "$CHECK_ONLY" = true ]; then
    overall_exit=0
    for t in claude-code codex cursor; do
        echo ""
        bash "$SCRIPT_DIR/install.sh" --target "$t" --check || overall_exit=$?
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
elif [ "$TARGET" = "all" ]; then
    : # install path handled after function definitions below
else
    echo "Unknown target: $TARGET (use 'claude-code', 'codex', 'cursor', or 'all')"
    exit 1
fi

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
        "$SCRIPT_DIR/src/coaching-ref.md"
    )
    local runtime_dests=(
        "$VALOR_HOME/evidence_cli.py"
        "$VALOR_HOME/career_framework.md"
        "$VALOR_HOME/utilities.md"
        "$VALOR_HOME/coaching-ref.md"
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

# --- Functions for --target all (single-pass install) ---

install_shared() {
    echo "Shared:"

    mkdir -p "$VALOR_HOME"
    mkdir -p "$VALOR_HOME/carry-forward"

    local detected_intg
    detected_intg=$(detect_integrations)

    local schema_version=3

    if [ ! -f "$VALOR_HOME/state.json" ]; then
        cat > "$VALOR_HOME/state.json" <<STATEJSON
{
  "state_schema_version": $schema_version,
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
  "integrations": $detected_intg,
  "last_update_check": "",
  "update_check_interval_hours": 24
}
STATEJSON
        echo "  [OK] state.json (created)"
    else
        local migrate_msg
        migrate_msg=$(python3 -c "
import json, sys
state = json.loads(open(sys.argv[1]).read())
target_version = int(sys.argv[2])
current_version = state.get('state_schema_version', 1)
changed = False
if current_version < 2:
    if 'integrations' not in state:
        state['integrations'] = json.loads(sys.argv[3])
        changed = True
    if 'state_schema_version' not in state:
        changed = True
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
    print(f'migrated to schema v{target_version}')
else:
    print('up to date')
" "$VALOR_HOME/state.json" "$schema_version" "$detected_intg" 2>/dev/null || echo "ok")
        echo "  [OK] state.json ($migrate_msg)"
    fi

    cp "$SCRIPT_DIR/src/evidence_cli.py" "$VALOR_HOME/evidence_cli.py"
    echo "  [OK] evidence_cli.py"

    if [ ! -f "$VALOR_HOME/career_framework.md" ]; then
        cp "$SCRIPT_DIR/src/career_framework.md" "$VALOR_HOME/career_framework.md"
        echo "  [OK] career_framework.md (template installed)"
    else
        echo "  [OK] career_framework.md (exists, not overwritten)"
    fi

    cp "$SCRIPT_DIR/src/utilities.md" "$VALOR_HOME/utilities.md"
    echo "  [OK] utilities.md"

    cp "$SCRIPT_DIR/src/coaching-ref.md" "$VALOR_HOME/coaching-ref.md"
    echo "  [OK] coaching-ref.md"

    # Record installed version
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
}

install_target_compact() {
    local t="$1"
    local label=""
    local cmd_count=${#COMMAND_MAP[@]}

    case "$t" in
        claude-code)
            label="Claude Code"
            local cdir="$HOME/.claude"
            local ccmds="$cdir/commands"
            mkdir -p "$cdir" "$ccmds"

            local marker_s="# --- BEGIN VALOR ---"
            local marker_e="# --- END VALOR ---"
            if [ -f "$cdir/CLAUDE.md" ] && grep -q "$marker_s" "$cdir/CLAUDE.md" 2>/dev/null; then
                local tmp_f
                tmp_f=$(mktemp)
                sed "/$marker_s/,/$marker_e/d" "$cdir/CLAUDE.md" > "$tmp_f"
                mv "$tmp_f" "$cdir/CLAUDE.md"
            fi
            { echo ""; echo "$marker_s"; cat "$RULE_SOURCE"; echo "$marker_e"; } >> "$cdir/CLAUDE.md"

            for entry in "${COMMAND_MAP[@]}"; do
                IFS=':' read -r src_name cc_name skill_name description <<< "$entry"
                cp "$SCRIPT_DIR/commands/$src_name.md" "$ccmds/$cc_name.md"
            done

            echo "$label:"
            echo "  [OK] Agent rule -> ~/.claude/CLAUDE.md"
            echo "  [OK] $cmd_count commands -> ~/.claude/commands/"
            ;;
        codex)
            label="Codex CLI"
            local cdir="$HOME/.codex"
            local cskills="$cdir/skills"
            mkdir -p "$cdir"

            local marker_s="# --- BEGIN VALOR ---"
            local marker_e="# --- END VALOR ---"
            if [ -f "$cdir/AGENTS.md" ] && grep -q "$marker_s" "$cdir/AGENTS.md" 2>/dev/null; then
                local tmp_f
                tmp_f=$(mktemp)
                sed "/$marker_s/,/$marker_e/d" "$cdir/AGENTS.md" > "$tmp_f"
                mv "$tmp_f" "$cdir/AGENTS.md"
            fi
            { echo ""; echo "$marker_s"; generate_codex_rule_content "$RULE_SOURCE"; echo "$marker_e"; } >> "$cdir/AGENTS.md"

            for entry in "${COMMAND_MAP[@]}"; do
                IFS=':' read -r src_name cc_name skill_name description <<< "$entry"
                mkdir -p "$cskills/$skill_name"
                generate_skill "$SCRIPT_DIR/commands/$src_name.md" \
                    "$cskills/$skill_name/SKILL.md" "$skill_name" "$description"
            done

            echo "$label:"
            echo "  [OK] Agent rule -> ~/.codex/AGENTS.md"
            echo "  [OK] $cmd_count skills -> ~/.codex/skills/"
            ;;
        cursor)
            label="Cursor"
            local crules="$HOME/.cursor/rules"
            local cskills="$HOME/.cursor/skills"
            mkdir -p "$crules"

            generate_cursor_rule "$RULE_SOURCE" "$crules/valor-agent.mdc"

            for entry in "${COMMAND_MAP[@]}"; do
                IFS=':' read -r src_name cc_name skill_name description <<< "$entry"
                mkdir -p "$cskills/$skill_name"
                generate_skill "$SCRIPT_DIR/commands/$src_name.md" \
                    "$cskills/$skill_name/SKILL.md" "$skill_name" "$description"
            done

            echo "$label:"
            echo "  [OK] Agent rule -> ~/.cursor/rules/valor-agent.mdc"
            echo "  [OK] $cmd_count skills -> ~/.cursor/skills/"
            ;;
    esac
}

# Run check_drift for a target, only print DRIFT/MISSING lines (silent if clean)
check_drift_quiet() {
    local t="$1"
    local saved_target="$TARGET"
    TARGET="$t"
    case "$t" in
        cursor)
            AGENT_RULES="$HOME/.cursor/rules"
            AGENT_SKILLS="$HOME/.cursor/skills"
            ;;
        codex)
            CODEX_DIR="$HOME/.codex"
            CODEX_SKILLS="$CODEX_DIR/skills"
            ;;
        claude-code)
            CLAUDE_DIR="$HOME/.claude"
            CLAUDE_COMMANDS="$CLAUDE_DIR/commands"
            ;;
    esac
    local output
    output=$(check_drift 2>&1) || true
    echo "$output" | grep -E '^\[(DRIFT|MISSING)' || true
    TARGET="$saved_target"
}

print_summary_all() {
    echo ""
    echo "=== Installed (v$VALOR_VERSION) ==="
    echo ""
    echo "Agents:"
    echo "  1. Morning Briefing  -- auto-suggests before 11am"
    echo "  2. PR Review Coach   -- 'review PR #NNN'"
    echo "  3. Design Doc Coach  -- 'design doc for TICKET'"
    echo "  4. Weekly Reflection -- auto-suggests Friday"
    echo "  5. Task Identifier   -- 'what should I work on'"
    echo "  6. Evening Wrap-up   -- auto-suggests after 4pm"
    echo "  7. 1:1 Prep          -- 'prep for 1:1'"
    echo "  8. Setup             -- /valor-setup or 'set up valor'"
    echo "  9. Ambient Coaching  -- always on ('valor quiet' to suppress)"
    echo ""
    echo "Next step: run /valor-setup (or say 'set up valor') in your agent"
    echo ""
    echo "Integrations:"
    python3 -c "
import json
from pathlib import Path
state = json.loads((Path.home() / '.valor' / 'state.json').read_text())
intg = state.get('integrations', {})
parts = []
for key, label in [('github', 'GitHub'), ('jira', 'Jira'), ('calendar', 'Calendar'), ('news', 'News')]:
    icon = '✓' if intg.get(key, False) else '✗'
    parts.append(f'{icon} {label}')
print('  ' + '    '.join(parts))
" 2>/dev/null || echo "  (could not read integrations)"
    echo ""
    echo "Data: $VALOR_HOME/"
}

# --- Handle --target all install (single-pass, compact output) ---
if [ "$TARGET" = "all" ]; then
    echo ""
    echo "=== Valor Installer ==="
    echo ""
    install_shared
    echo ""
    for t in claude-code codex cursor; do
        install_target_compact "$t"
    done
    # Quiet drift check -- only show problems (deduplicate shared-file lines)
    drift_issues=""
    for t in claude-code codex cursor; do
        drift_issues+="$(check_drift_quiet "$t")"$'\n'
    done
    drift_issues=$(echo "$drift_issues" | sort -u | sed '/^$/d')
    if [ -n "$drift_issues" ]; then
        echo ""
        echo "Drift detected:"
        echo "$drift_issues"
    fi
    print_summary_all
    exit 0
fi

# --- Single-target flow below ---

if [ "$CHECK_ONLY" = true ]; then
    echo "=== Valor Drift Check ($TARGET) ==="
    echo ""
    check_drift
    exit $?
fi

echo "=== Valor Installer ($TARGET) ==="
echo ""
install_shared
echo ""
install_target_compact "$TARGET"
# Quiet drift check -- only show problems
drift_issues=$(check_drift_quiet "$TARGET")
if [ -n "$drift_issues" ]; then
    echo ""
    echo "Drift detected:"
    echo "$drift_issues"
fi
print_summary_all
