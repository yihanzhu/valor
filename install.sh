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
#   ./install.sh --upgrade                    Check for a newer release + show how to update (notify-only)
#   ./install.sh --auto-update                Notify if a newer release exists (agent-triggered; notify-only)
#
# Updates are NOTIFY-ONLY. Valor never silently tracks `main` HEAD or checks out
# a tag for you -- it tells you when a newer RELEASE (tagged vX.Y.Z) is available,
# and you update manually. With no release tagged yet (or offline) the check is a
# clean no-op.
#
# Update to the latest release manually:
#   git -C ~/.valor/repo fetch --tags && git -C ~/.valor/repo checkout vX.Y.Z && bash ~/.valor/repo/install.sh
# Pin a version (stop the daily check from nudging you off it):
#   set "update_check_interval_hours": 0 in ~/.valor/state.json
#
# Quick install (clones repo then installs):
#   curl -fsSL https://raw.githubusercontent.com/yihanzhu/valor/main/install.sh | bash -s -- --clone
# It's a short shell script -- read it before piping to bash:
#   curl -fsSL .../main/install.sh | less

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VALOR_HOME="$HOME/.valor"
VALOR_REPO="https://github.com/yihanzhu/valor.git"
VALOR_CLONE_DIR="$VALOR_HOME/repo"

# --- Release-update notification (notify-only; never self-mutates) ----------
# Valor never silently pulls `main` or checks out a tag. These helpers only
# *look*: they resolve origin's latest RELEASE tag (vX.Y.Z) and, when it is newer
# than the installed VERSION, tell the user how to update and pin -- manually.
# The semver-aware "which tag is latest / is it newer" logic lives in the pure,
# tested scripts/latest_release_tag.py; here we just query origin and format the
# message. Offline, no release tagged yet, and already-current all degrade to a
# clean no-op -- nothing is ever fetched, checked out, or re-installed.

# Print origin's latest release tag IF it is strictly newer than the version
# installed in repo $1; otherwise print nothing. Never fetches, checks out, or
# mutates anything. A missing resolver, an unreachable origin, or no-newer-release
# all yield empty output (return 0), so callers cleanly no-op.
resolve_newer_release() {
    local repo_dir="$1"
    local resolver="$SCRIPT_DIR/scripts/latest_release_tag.py"
    [ -f "$resolver" ] || return 0
    local installed
    installed="$(cat "$repo_dir/VERSION" 2>/dev/null || echo "unknown")"
    # ls-remote reads origin's CURRENT tags; on failure (offline) the pipe is
    # empty and the resolver prints nothing. `--installed` makes the resolver emit
    # the latest tag only when it is strictly newer than $installed.
    git -C "$repo_dir" ls-remote --tags origin 2>/dev/null \
        | python3 "$resolver" --installed "$installed" 2>/dev/null || true
}

# Print manual update + pin instructions for a newer release $2 (installed $3, in
# repo $1). Notify-only: it prints commands for the user to run, never runs them.
print_update_instructions() {
    local repo_dir="$1" tag="$2" installed="$3"
    echo "A new Valor release is available: $tag (installed: $installed)."
    echo "  Update:  git -C $repo_dir fetch --tags && git -C $repo_dir checkout $tag && bash $repo_dir/install.sh"
    echo "  Pin:     after checkout, set \"update_check_interval_hours\": 0 in ~/.valor/state.json"
}

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
    "wrapup:valor-wrapup:valor-evening-wrapup:Valor evening wrap-up: summarizes the day's work, captures carry-forward items for tomorrow, and reflects on competencies exercised"
    "prep:valor-prep:valor-prep:Valor 1:1 prep: generates a structured document for manager 1:1s grounded in evidence, weekly summaries, and career framework alignment"
    "sync-prep:valor-sync-prep:valor-sync-prep:Valor project sync prep: generates team-facing talk points for an upcoming project sync (progress since last sync, decisions to land, open questions) for the user to review and share"
    "reflection:valor-reflection:valor-performance-reflection:Valor performance reflection: turns the cycle's evidence log into a review-ready self-reflection draft (impact themes mapped to competency and company value) plus a confirm-before-submit list of status/role uncertainties"
    "upward-feedback:valor-upward-feedback:valor-upward-feedback:Valor upward feedback: assembles a draft of feedback about your manager for a review cycle, grounded in observed behaviors from meeting notes and 1:1 evidence, for you to review and paste"
    "setup:valor-setup:valor-setup:Valor setup: guided configuration of career framework, levels, and integrations"
    "pr-console:valor-pr-console:valor-pr-review-console:Valor PR review console: turns a pull request into an interactive C4 diagram (Context to Component to real code) plus a coverage-driven, answer-verified mastery quiz that gates approval on understanding"
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
            echo "=== Valor Update Check ==="
            echo ""
            # Notify-only: report whether a newer release exists and how to apply
            # it. Never pulls `main`, checks out a tag, or re-installs.
            if [ -d "$SCRIPT_DIR/.git" ]; then
                installed="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo "unknown")"
                newer="$(resolve_newer_release "$SCRIPT_DIR")"
                if [ -n "$newer" ]; then
                    print_update_instructions "$SCRIPT_DIR" "$newer" "$installed"
                else
                    echo "Valor is up to date (installed $installed) -- no newer release tagged (or offline)."
                fi
            else
                echo "Not a git repo -- clone from $VALOR_REPO first, then update manually."
                exit 1
            fi
            exit 0
            ;;
        --auto-update)
            # Notify-only (agent-triggered). Stays silent unless a newer release
            # exists; never pulls `main`, checks out a tag, or re-installs.
            repo_dir="$VALOR_HOME/repo"
            if [ -d "$repo_dir/.git" ]; then
                installed="$(cat "$repo_dir/VERSION" 2>/dev/null || echo "unknown")"
                newer="$(resolve_newer_release "$repo_dir")"
                if [ -n "$newer" ]; then
                    print_update_instructions "$repo_dir" "$newer" "$installed"
                fi
                # No newer release / no release tagged yet / offline: clean no-op.
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
        -e 's|/valor-wrapup|valor-evening-wrapup skill|g' \
        -e 's|/valor-sync-prep|valor-sync-prep skill|g' \
        -e 's|/valor-reflection|valor-performance-reflection skill|g' \
        -e 's|/valor-upward-feedback|valor-upward-feedback skill|g' \
        -e 's|/valor-prep|valor-prep skill|g' \
        -e 's|/valor-setup|valor-setup skill|g' \
        -e 's|/valor-pr-console|valor-pr-review-console skill|g' \
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
        -e "s|\`/valor-wrapup\` command|\`~/$target_dir/skills/valor-evening-wrapup/SKILL.md\`|g" \
        -e "s|\`/valor-sync-prep\` command|\`~/$target_dir/skills/valor-sync-prep/SKILL.md\`|g" \
        -e "s|\`/valor-reflection\` command|\`~/$target_dir/skills/valor-performance-reflection/SKILL.md\`|g" \
        -e "s|\`/valor-upward-feedback\` command|\`~/$target_dir/skills/valor-upward-feedback/SKILL.md\`|g" \
        -e "s|\`/valor-prep\` command|\`~/$target_dir/skills/valor-prep/SKILL.md\`|g" \
        -e "s|\`/valor-setup\` command|\`~/$target_dir/skills/valor-setup/SKILL.md\`|g" \
        -e "s|\`/valor-pr-console\` command|\`~/$target_dir/skills/valor-pr-review-console/SKILL.md\`|g"
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
        "$SCRIPT_DIR/src/verify.py"
        "$SCRIPT_DIR/src/plan.py"
        "$SCRIPT_DIR/src/focus.py"
        "$SCRIPT_DIR/src/collect_transcripts.py"
        "$SCRIPT_DIR/src/career_framework.md"
        "$SCRIPT_DIR/src/utilities.md"
        "$SCRIPT_DIR/src/coaching-ref.md"
        "$SCRIPT_DIR/src/pr-console/template.html"
        "$SCRIPT_DIR/src/pr-console/generate.js"
        "$SCRIPT_DIR/src/pr-console/assemble.py"
    )
    local runtime_dests=(
        "$VALOR_HOME/evidence_cli.py"
        "$VALOR_HOME/verify.py"
        "$VALOR_HOME/plan.py"
        "$VALOR_HOME/focus.py"
        "$VALOR_HOME/collect_transcripts.py"
        "$VALOR_HOME/career_framework.md"
        "$VALOR_HOME/utilities.md"
        "$VALOR_HOME/coaching-ref.md"
        "$VALOR_HOME/pr-console/template.html"
        "$VALOR_HOME/pr-console/generate.js"
        "$VALOR_HOME/pr-console/assemble.py"
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

    # Schema version is owned by evidence_cli.py (STATE_SCHEMA_VERSION); read it
    # instead of hardcoding a second literal that could silently drift (M24).
    # `|| true` keeps a no-match (constant renamed/file moved) from aborting the
    # whole install under `set -euo pipefail`, so the fallback below can run.
    local schema_version
    schema_version=$(grep -oE 'STATE_SCHEMA_VERSION *= *[0-9]+' "$SCRIPT_DIR/src/evidence_cli.py" | grep -oE '[0-9]+' | head -1 || true)
    if [ -z "$schema_version" ]; then schema_version=1; fi

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
  "update_check_interval_hours": 24,
  "verification": {
    "enabled": true,
    "escalation_threshold": 3,
    "ttl_overrides": {}
  },
  "escalate_in_one_on_one": [],
  "planning": {
    "calendar_auto_write": true,
    "workday_start": "09:00",
    "workday_end": "18:00",
    "deep_min_hours": 2.0,
    "post_meeting_break_minutes": 15,
    "block_granularity_minutes": 15,
    "morning_buffer_minutes": 0,
    "pre_meeting_prep_minutes": 30
  },
  "one_on_one": {
    "doc": "",
    "format_notes": ""
  },
  "project_focus": {
    "enabled": false,
    "mode": "meeting_derived",
    "current": "",
    "flip": "after_sync",
    "syncs": [],
    "auto_sync_prep": true,
    "parked_projects": [],
    "meeting_catalog": []
  },
  "prioritization": {
    "week_goals": [],
    "week_start": "",
    "goals_source": ""
  },
  "standing_rules": []
}
STATEJSON
        echo "  [OK] state.json (created)"
    fi

    # Schema migration: the SINGLE source of truth is
    # evidence_cli._migrate_state_in_memory. install.sh no longer carries a
    # duplicate inline migrator (the two had drifted to different key sets).
    # Delegate to the source CLI; it migrates ~/.valor/state.json in place and
    # self-heals a freshly-created file too if the template ever lags the schema.
    local migrate_out
    if migrate_out=$(python3 "$SCRIPT_DIR/src/evidence_cli.py" state-migrate 2>&1); then
        echo "  [OK] state.json (schema v$schema_version)"
        # Surface any warning lines (e.g. a corrupt state.json quarantined to a
        # backup); the normal status line is JSON, which we don't echo.
        printf '%s\n' "$migrate_out" | grep -v '^{' | grep . | sed 's/^/      /' || true
    else
        echo "  [WARN] state.json schema migration failed; existing file left untouched:"
        printf '%s\n' "$migrate_out" | sed 's/^/        /'
    fi

    # Integration DETECTION is install-specific (the CLI can't probe for the gh
    # binary). Seed detected integrations only when the field is absent or empty,
    # so a re-run won't overwrite a user's configured integrations.
    python3 - "$VALOR_HOME/state.json" "$detected_intg" <<'PYEOF'
import json, sys
path, detected = sys.argv[1], sys.argv[2]
try:
    state = json.loads(open(path).read())
except Exception:
    sys.exit(0)
if not isinstance(state, dict):
    sys.exit(0)
if not isinstance(state.get("integrations"), dict) or not state["integrations"]:
    state["integrations"] = json.loads(detected)
    with open(path, "w") as f:
        f.write(json.dumps(state, indent=2))
PYEOF

    cp "$SCRIPT_DIR/src/evidence_cli.py" "$VALOR_HOME/evidence_cli.py"
    echo "  [OK] evidence_cli.py"

    cp "$SCRIPT_DIR/src/verify.py" "$VALOR_HOME/verify.py"
    echo "  [OK] verify.py"

    cp "$SCRIPT_DIR/src/plan.py" "$VALOR_HOME/plan.py"
    echo "  [OK] plan.py"

    cp "$SCRIPT_DIR/src/focus.py" "$VALOR_HOME/focus.py"
    echo "  [OK] focus.py"

    cp "$SCRIPT_DIR/src/collect_transcripts.py" "$VALOR_HOME/collect_transcripts.py"
    echo "  [OK] collect_transcripts.py"

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

    # PR review console assets (used by /valor-pr-console): renderer template,
    # generator workflow, and deterministic layout+inject script.
    mkdir -p "$VALOR_HOME/pr-console"
    cp "$SCRIPT_DIR/src/pr-console/template.html" "$VALOR_HOME/pr-console/template.html"
    cp "$SCRIPT_DIR/src/pr-console/generate.js"   "$VALOR_HOME/pr-console/generate.js"
    cp "$SCRIPT_DIR/src/pr-console/assemble.py"   "$VALOR_HOME/pr-console/assemble.py"
    echo "  [OK] pr-console/ (template + generator + assembler)"

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

# Remove orphaned Valor artifacts left behind by a RETIRED command, so retiring a
# command self-cleans instead of lingering on every host. STRICTLY scoped: only
# touches the `valor-*` names Valor generates, and only those NOT in the current
# COMMAND_MAP — a user's own (non-`valor-`) commands/skills are never removed.
prune_orphans() {
    local kind="$1" dir="$2"   # kind: command (valor-*.md files) | skill (valor-*/ dirs)
    [ -d "$dir" ] || return 0
    local expected=" " entry src cc sk desc
    for entry in "${COMMAND_MAP[@]}"; do
        IFS=':' read -r src cc sk desc <<< "$entry"
        if [ "$kind" = command ]; then expected+="$cc "; else expected+="$sk "; fi
    done
    local path name
    if [ "$kind" = command ]; then
        for path in "$dir"/valor-*.md; do
            [ -e "$path" ] || continue
            name=$(basename "$path" .md)
            case "$expected" in
                *" $name "*) : ;;
                *) rm -f "$path"; echo "  [prune] removed retired command ${path##*/}" ;;
            esac
        done
    else
        for path in "$dir"/valor-*/; do
            [ -e "$path" ] || continue
            name=$(basename "$path")
            case "$expected" in
                *" $name "*) : ;;
                # Strip the trailing slash and pass `--`: on a *symlinked* dir, `rm -rf`
                # with a trailing slash dereferences the link and deletes the TARGET's
                # contents (which may live outside this dir). `${path%/}` makes rm act on
                # the entry itself, so a retired symlink is merely unlinked.
                *) rm -rf -- "${path%/}"; echo "  [prune] removed retired skill $name" ;;
            esac
        done
    fi
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
            prune_orphans command "$ccmds"

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
            prune_orphans skill "$cskills"

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
            prune_orphans skill "$cskills"

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
    echo "  5. Evening Wrap-up   -- auto-suggests after 4pm"
    echo "  6. 1:1 Prep          -- 'prep for 1:1'"
    echo "  7. Project Sync Prep -- 'sync prep' before a project sync"
    echo "  8. Performance Reflection -- 'half-year reflection' at review time"
    echo "  9. Upward Feedback   -- 'feedback about my manager' at review time"
    echo "  10. Setup            -- /valor-setup or 'set up valor'"
    echo "  11. PR Review Console -- 'build a review console for #NNN'"
    echo "  12. Ambient Coaching -- always on ('valor quiet' to suppress)"
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
