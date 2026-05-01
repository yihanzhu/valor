# Valor Setup

Guided setup that configures Valor's career framework, levels, and
integrations. Re-runnable -- checks what is already configured and walks
through what is missing.

## 0. Check Current State

Run the setup status command to see what is already configured:

```bash
python3 ~/.valor/evidence_cli.py setup-status
```

This returns a JSON blob:
- `framework_is_template` -- `true` if `career_framework.md` is still the
  unedited template (contains placeholder brackets)
- `framework_levels` -- list of level headings found in the framework
  (e.g. `["L3 - Software Engineer", "L4 - Senior Software Engineer"]`)
- `levels_configured` -- `true` if all three level fields are non-empty
- `current_level`, `target_level`, `ceiling_level` -- current values
- `github_owner`, `jira_projects`, `integrations` -- current config

Use this to decide which sections to run:
- `framework_is_template == true` -> run section 1 (Career Framework)
- `levels_configured == false` -> run section 2 (Level Selection)
- Both done + `github_owner` and `jira_projects` empty -> run section 3
- All of the above done + no `routines` configured for any slot -> offer
  section 4 (Routines)

If everything appears configured, tell the user: "Valor looks fully set up.
Want to reconfigure anything? (career framework / levels / integrations /
routines / skip)"

If the user says "redo routines" at any time, skip directly to section 4.

## 1. Career Framework

This is the most important step. Valor's coaching quality depends entirely
on having a real career framework.

### Check if already configured

From the `setup-status` output:
- If `framework_is_template` is `true`, the framework needs to be replaced.
- If `framework_is_template` is `false`, ask: "Your career framework is
  already configured with [N] levels. Do you want to reconfigure it?
  (say 'skip' to keep the current one)"

### Gather the user's career ladder

Ask: "Do you have your company's career ladder document? You can:
1. **Paste the text** directly into this chat
2. **Describe your levels** and I'll help structure them
3. **Use a generic template** and customize later"

**If the user pastes text or describes their ladder:**

Transform it into `career_framework.md` format. The output MUST follow
this structure for every level:

```markdown
### [Level Code] - [Title]

**Role summary:** [2-3 sentences about what this level does]

**Competencies:**

- **Subject Matter Expertise:** [technical expectations]
- **Industry Knowledge:** [tools, methods, trends awareness]
- **Internal Collaboration:** [cross-team, communication expectations]
- **Autonomy & Scope:** [independence, ownership expectations]
- **Leadership:** [mentoring, influence, decision-making expectations]
```

Rules for transformation:
- Preserve the company's original level codes (L3, IC4, E5, etc.)
- Map their competency categories to Valor's five axes as closely as possible
- If the source has fewer than 5 competency axes, infer reasonable
  expectations from the role summary and adjacent levels
- If the source has more than 5, merge related ones into the closest axis
- **Preserve detail**: each competency description should be 2-4 sentences
  that capture the specific expectations from the source. Do NOT compress
  multi-sentence descriptions into one-liners. Valor coaching references
  these descriptions directly -- more detail means better coaching.
- Include at least 3 levels (current, target, ceiling) -- more is fine
- Include company values if the user provides them, as `### [Value Name]`
  sections under a `## Company Values` heading

**If the user wants a generic template:**

Ask what level codes their company uses (e.g. IC3-IC5, L3-L5, E3-E5) and
their job title (e.g. "Software Engineer", "Data Scientist"). Then generate
a 3-level ladder where:
- Level 1: executes tasks with guidance, writes clean code, basic collaboration
- Level 2: converts requirements into designs, leads moderate features, mentors
- Level 3: designs complex systems, cross-team impact, strategic influence

Use generic company values ("Excellence", "Collaboration", "Ownership") as
placeholders. Tell the user they can edit `~/.valor/career_framework.md`
later to customize.

### Write the framework

The complete file MUST have this overall structure:

```markdown
# Career Framework

## Levels

### [Level] - [Title]
...competencies...

### [Level] - [Title]
...competencies...

---

## Company Values

### [Value Name]
[Description]

---

## Guidance
[Optional: years of experience guidelines, promotion timeline]
```

Show the generated framework to the user and ask for confirmation:
"Here's your career framework. Does this look right? (I can adjust any
section before saving)"

After confirmation, write to `~/.valor/career_framework.md`.

## 2. Level Selection

After the career framework is written, re-run `setup-status` to get the
updated `framework_levels` list.

Present the levels to the user:
"I found these levels in your framework: [list]. Which one are you at now?"

Then ask: "Which level are you working toward?"

Set `ceiling_level` to one level above target (if it exists in the
framework). If target is already the highest level, set ceiling to the
same as target.

Apply with:

```bash
python3 ~/.valor/evidence_cli.py state-set \
  current_level "[CURRENT]" \
  target_level "[TARGET]" \
  ceiling_level "[CEILING]"
```

Verify by running:

```bash
python3 ~/.valor/evidence_cli.py framework-slice
```

Confirm the output shows the correct level definitions. If `framework-slice`
returns "(Not found in career framework)" for any level, the level code
does not match a heading -- fix the mismatch before proceeding.

## 3. Integrations

### GitHub

Check if `gh` CLI is available:

```bash
gh auth status 2>&1
```

If authenticated, ask: "What's your GitHub organization name? (for
cross-team PR discovery -- leave blank to skip)"

If provided, set it:

```bash
python3 ~/.valor/evidence_cli.py state-set github_owner "[ORG]"
```

If `gh` is not available or not authenticated, tell the user: "GitHub
integration disabled. Run `gh auth login` and re-run `/valor-setup` to
enable it later."

### Jira

Ask: "Do you use Jira? If so, what are your project keys? (e.g. PROJ, ENG
-- comma-separated, or 'no' to disable)"

If yes with keys:

```bash
python3 ~/.valor/evidence_cli.py state-set jira_projects '["PROJ","ENG"]'
```

If no, set Jira to disabled (see Applying Changes below).

### Calendar and News

Ask two yes/no questions:
1. "Do you have a Google Calendar plugin in your agent? (used for
   schedule-aware briefings)"
2. "Do you have web search available? (used for tech news in briefings)"

### Manager identity (optional)

Ask: "Who's your manager? (optional -- used to find your 1:1 in calendar.
Provide name, email, or both -- or say 'skip')"

If the user provides any value, save it:

```bash
python3 ~/.valor/evidence_cli.py state-set \
  manager '{"email":"manager@example.com","name":"Sam"}'
```

Replace the values with what the user actually provided. Use `null` for any
field they omit (e.g. `'{"email":"manager@example.com","name":null}'`). If
they say "skip", do not call `state-set` for this field.

This field is used only by 1:1 auto-detection in section 4 (Routines). It is
safe to skip and add later -- detection still works using recurrence and
title heuristics, just with lower precision.

### Applying integration changes

After collecting all answers, build the final integrations object. Start
from `context.integrations` and apply the user's answers:

- `github`: `true` if `gh auth status` succeeded, `false` otherwise
- `jira`: `true` if user provided project keys, `false` if they said no
- `calendar`: `true` if user said yes, `false` if no
- `news`: `true` if user said yes, `false` if no

Write all four flags in one call:

```bash
python3 ~/.valor/evidence_cli.py state-set \
  integrations '{"github":true,"jira":false,"calendar":true,"news":true}'
```

Replace each boolean with the actual value determined above.

## 4. Routines

Valor has four time-anchored agents that deliver the most value when run on a
recurring schedule. This section provisions them on the host's scheduled-task
runtime so the user does not have to set them up by hand.

| Slot | taskId | description | prompt | default cron |
|------|--------|-------------|--------|--------------|
| `briefing` | `valor-morning-briefing` | `Valor Morning Briefing` | `/valor-briefing` | `0 9 * * 1-5` |
| `wrapup` | `valor-evening-wrap-up` | `Valor Evening Wrap-up` | `/valor-wrapup` | `0 17 * * 1-5` |
| `weekly` | `valor-weekly-reflection` | `Valor Weekly Reflection` | `/valor-weekly` | `30 16 * * 5` |
| `prep` | `valor-prep` | `Valor 1:1 Prep` | `/valor-prep` | derived from 1:1 time |

Cron expressions are evaluated in the user's local timezone (the host
runtime handles this; do not ask for a timezone).

### 4.1 Migrate state schema

Ensure `state.json` has the v4 fields (`routines`, `manager`, `host`). This
is idempotent and safe to re-run:

```bash
python3 ~/.valor/evidence_cli.py state-migrate
```

### 4.2 Detect host

Detect which agent host is running:
- If `$CLAUDECODE` is `1`, host is `claude-code`. Phase 1 supports this host.
- If the `codex` CLI is on PATH and authenticated, host is `codex`. **Codex
  routine provisioning is Phase 2 and not yet supported by this skill** --
  skip routine setup and tell the user: "Codex auto-provisioning is coming;
  for now, set up routines via the Codex Automations UI."
- Otherwise, host is unsupported. Skip routine setup and tell the user:
  "Routine auto-provisioning isn't available on this host. You can still run
  the four agents on demand."

If host is `claude-code`, persist it and continue:

```bash
python3 ~/.valor/evidence_cli.py state-set host "claude-code"
```

### 4.3 Probe existing routines

List existing scheduled tasks via the
`mcp__scheduled-tasks__list_scheduled_tasks` tool. Filter to entries whose
`taskId` starts with `valor-`. For each match:

1. Read the entry's prompt body to infer the slot:
   - prompt contains `/valor-briefing` -> `briefing`
   - prompt contains `/valor-wrapup` -> `wrapup`
   - prompt contains `/valor-weekly` -> `weekly`
   - prompt contains `/valor-prep` -> `prep`
2. Cross-reference against `routines.<slot>` in `state.json`:
   - **In state, same `cron` and `task_id`** -> skip silently.
   - **In state, different config** -> ask: update / recreate / skip.
   - **Not in state, taskId is canonical** -> auto-link to state (no prompt).
   - **Not in state, taskId is non-canonical** (e.g. `valor-11-prep` for the
     prep slot) -> offer: rename to canonical (e.g. `valor-prep`) / leave
     as-is and link / skip.
3. **Auto-link on first post-upgrade run:** when the user installs this
   upgrade for the first time and existing UI-created routines are detected,
   link them to state silently rather than asking. The user can re-trigger
   the flow by saying "redo routines".

To rename a non-canonical taskId, update via
`mcp__scheduled-tasks__update_scheduled_task` is not sufficient -- taskId
is not editable. Instead, create the canonical taskId, then ask the user to
delete the old one in the host UI (no API for delete in Phase 1).

### 4.4 Routine menu

Show the four routines with brief descriptions and ask which to enable.
Default is all on:

```
Valor can set up 4 recurring routines for you. Pick which ones you want:

  [x] Morning briefing      Mon-Fri 09:00          /valor-briefing
  [x] Evening wrap-up       Mon-Fri 17:00          /valor-wrapup
  [x] Weekly reflection     Fri 16:30 (or Sun pm)  /valor-weekly
  [x] 1:1 prep              90 min before your 1:1 /valor-prep
```

If a routine is already provisioned (from §4.3), mark it as such and ask
whether to keep, update, or remove.

### 4.5 1:1 auto-detection (only if `prep` is enabled)

Valor does not have a direct calendar API. Reuse the same pattern the
briefing skill uses: discover whichever calendar slash-command plugin the
user has installed.

1. Look for installed slash-commands matching `*google*` or `*calendar*`.
   If none is found, fall back to manual entry (skip to step 5) and tell the
   user: "No calendar plugin found -- install one and re-run setup to
   auto-detect your 1:1."
2. Invoke the discovered plugin to fetch events for the **next 4 weeks**.
3. Group events by `(title, other_attendee_email)` after dropping the
   user's own email. Filter to groups with **>= 3 occurrences** -- this
   captures weekly cadence without parsing recurrence rules.
4. Score each candidate group:

   | Signal | Weight |
   |--------|--------|
   | Group size >= 3 in 4 weeks | required |
   | Exactly 2 attendees per occurrence | +3 |
   | Title regex `\b(1[:/-]?1\|one[ -]on[ -]one)\b` (case-insensitive) | +3 |
   | Title contains both attendee names or `name1 / name2` | +2 |
   | Other attendee matches `state.manager.email` | +5 |
   | Modal duration 25-60 min | +1 |

   Decision:
   - Best score >= 5 and second-best is at least 2 points behind -> **propose** the best.
   - Two or more candidates within 2 points of each other -> **list** all, ask the user to pick.
   - Otherwise -> manual entry.

5. **Propose path UX:**

   ```
   Found your weekly 1:1: "Alex / Sam -- 1:1"
     Mondays 11:00, with manager@example.com

     -> Prep will run Mondays 09:30 (90 min before).

   Use this? [Y / edit / manual]
   ```

   `edit` lets the user adjust lead-time or pick a different candidate;
   `manual` skips detection and asks for day + time directly.

6. **Manual entry fallback:** ask "What day and time is your weekly 1:1?
   (e.g. 'Monday 11:00')" and "Lead time before the meeting? (default 90
   min)".

7. Record the result in `routines.prep.personalization`:
   - `one_on_one_day`, `one_on_one_time` -- always set
   - `lead_minutes` -- default 90
   - `source` -- `"calendar"` if auto-detected, `"user"` if manual,
     `"calendar+user-edited"` if auto-detected then edited
   - `calendar_event_id` -- if `source` is `"calendar"` or
     `"calendar+user-edited"`, store the plugin's event id for later drift
     checks; else `null`
   - `detected_at` -- ISO timestamp

### 4.6 Personalization for the other routines

Only ask for what is relevant to the routines the user kept. Defaults:

| Field | Routine | Default |
|-------|---------|---------|
| Briefing time | briefing | 09:00 |
| Wrap-up time | wrapup | 17:00 |
| Weekly slot | weekly | Friday 16:30 (alt: Sunday 19:00) |

Convert the user's personalization to a cron expression. Examples:

- Briefing 09:00 weekdays -> `0 9 * * 1-5`
- Wrap-up 17:00 weekdays -> `0 17 * * 1-5`
- Weekly Friday 16:30 -> `30 16 * * 5`
- Weekly Sunday 19:00 -> `0 19 * * 0`
- Prep, 1:1 Monday 11:00, lead 90 min -> 09:30 Monday -> `30 9 * * 1`

### 4.7 Permission-mode posture check

Routines run in their own session, inheriting the user's default permission
mode. The create API does **not** accept a per-task override.

Read the user's default mode from `~/.claude/settings.json`:

```bash
python3 -c "
import json, sys
from pathlib import Path
p = Path.home() / '.claude' / 'settings.json'
if p.exists():
    s = json.loads(p.read_text())
    print((s.get('permissions') or {}).get('defaultMode', 'default'))
else:
    print('default')
"
```

- If the result is `default` -> warn:

  ```
  Your Claude Code default permission mode is "default", which prompts on
  every tool call. Routines run unattended and will stall on the first prompt.

  Recommended: set defaultMode to "auto" (auto-approves tool calls but keeps
  destructive-action guardrails). You can change this with the update-config
  skill or in your settings.json.

  Continue anyway? [y/N]
  ```

  Default to N. Do **not** auto-edit the user's settings -- the user owns
  that decision.

- If the result is `acceptEdits`, `auto`, or `bypass` -> proceed silently.

### 4.8 Preview

Before any API call, render the full plan as a single block:

```
About to create routines on Claude Code:

  valor-morning-briefing    Mon-Fri 09:00         /valor-briefing
  valor-evening-wrap-up     Mon-Fri 17:00         /valor-wrapup
  valor-weekly-reflection   Fri 16:30             /valor-weekly
  valor-prep                Mon 09:30             /valor-prep
                            (90 min before your 1:1: Mon 11:00)

Permission mode (inherited): auto
All routines run in your local timezone.

Proceed? [Y / n / edit]
```

`edit` returns to §4.4. `Y` proceeds to §4.9. `n` writes nothing.

### 4.9 Provision

For each enabled routine, in order, call
`mcp__scheduled-tasks__create_scheduled_task` with these fields:

| Field | Value |
|-------|-------|
| `taskId` | canonical taskId for the slot (e.g. `valor-morning-briefing`) |
| `description` | canonical description (e.g. `Valor Morning Briefing`) |
| `prompt` | the slash command (e.g. `/valor-briefing`) |
| `cronExpression` | computed cron string |

Do **not** pass `title`, `timezone`, `working_directory`, or
`permission_mode` -- those fields are not in the API schema.

**Continue past failures.** Never abort the batch on a single error. After
each call:

- **Success:** record in state via:

  ```bash
  python3 ~/.valor/evidence_cli.py state-set routines '<UPDATED_ROUTINES_JSON>'
  ```

  where `<UPDATED_ROUTINES_JSON>` is the full `routines` object with the
  new entry merged in. Each slot entry has shape:

  ```json
  {
    "enabled": true,
    "host": "claude-code",
    "task_id": "valor-morning-briefing",
    "description": "Valor Morning Briefing",
    "cron": "0 9 * * 1-5",
    "last_provisioned_at": "<ISO timestamp>",
    "personalization": { "time": "09:00" }
  }
  ```

  For the prep slot, `personalization` also includes `one_on_one_day`,
  `one_on_one_time`, `lead_minutes`, `source`, `calendar_event_id`, and
  `detected_at` from §4.5.

- **Failure:** render the fallback paste-block (below). Do not retry
  automatically.

After the batch, summarize:

```
Routine setup
-------------
[v] valor-morning-briefing     created
[v] valor-evening-wrap-up      created
[!] valor-weekly-reflection    API error -- see paste-block below
[v] valor-prep                 created
```

Then print fallback paste-blocks for any failures, plus: "To retry just the
routines later, say 'redo routines'."

### 4.10 Fallback paste-block

When an API call fails, render a copy-paste block matching the host UI's
field labels:

```
-----------------------------------------------------------------
 Couldn't create this routine via API. Create it manually:
 1. Open Claude Code -> Settings -> Routines -> + New Routine
 2. Fill in:

    Name:         valor-morning-briefing
    Description:  Valor Morning Briefing
    Prompt:       /valor-briefing
    Schedule:     0 9 * * 1-5     (cron, local time)

 3. Save.
-----------------------------------------------------------------
```

Replace the four field values with whichever routine failed. Do not
include working-dir / permission-mode / timezone -- those are not UI fields
either.

### 4.11 Re-running just the routines

If the user says "redo routines" or runs `/valor-setup` and only wants to
update the routines section, skip §1-§3 and start at §4.1. The idempotency
logic in §4.3 handles existing routines correctly.

## 5. Verification

Run the validation and context checks:

```bash
python3 ~/.valor/evidence_cli.py framework-validate
python3 ~/.valor/evidence_cli.py context
```

`framework-validate` returns JSON with `valid`, `errors`, `warnings`, and
`levels_found`. If `valid` is `false`, fix the errors before proceeding.
Common errors:
- Missing `## Levels` section marker -> add it above the first `### ` heading
- Missing competencies -> add the missing axes to the level
- Configured level not in headings -> fix the level code in state or framework

If valid, present a summary:

```
Valor Setup Complete
--------------------
Career framework: [N] levels configured
Current level:    [CURRENT] - [Title]
Target level:     [TARGET] - [Title]
Ceiling level:    [CEILING] - [Title]
GitHub:           [enabled/disabled] (org: [ORG])
Jira:             [enabled/disabled] (projects: [KEYS])
Calendar:         [enabled/disabled]
News:             [enabled/disabled]
Manager:          [set/unset]
Host:             [claude-code/codex/unsupported]
Routines:         [N of 4] provisioned
                    briefing  -> [taskId or "not set"]
                    wrapup    -> [taskId or "not set"]
                    weekly    -> [taskId or "not set"]
                    prep      -> [taskId or "not set"]
```

Read these values from `setup-status` output (it includes `manager_set`,
`host`, and a per-slot `routines` object).

Then show the available agents and suggest next steps:

```
Your Valor agents:
  1. Morning Briefing  -- auto-suggests before 11am
  2. PR Review Coach   -- 'review PR #NNN'
  3. Design Doc Coach  -- 'design doc for TICKET'
  4. Weekly Reflection -- auto-suggests Friday
  5. Task Identifier   -- 'what should I work on'
  6. Evening Wrap-up   -- auto-suggests after 4pm
  7. 1:1 Prep          -- 'prep for 1:1'
  8. Setup             -- /valor-setup or 'set up valor'
  9. Ambient Coaching  -- always on ('valor quiet' to suppress)
```

- "Try: 'morning briefing' to see your first briefing"
- "Agents 1, 4, and 6 auto-suggest at the right time -- just start a conversation"
- "Say 'valor quiet' anytime to suppress coaching for a conversation"
- "Say 'valor off' to disable coaching entirely (re-enable with 'valor on')"

## Fallbacks

| Scenario | Action |
|----------|--------|
| User can't find their career ladder | Offer the generic template, note they can customize later |
| User's ladder has different competency axes | Map to the closest of the five axes, explain the mapping |
| User doesn't know their level code | Help them identify it from the framework descriptions |
| framework-slice returns "Not found" | Level code mismatch -- check if heading uses a different format (e.g. "L3" vs "IC3") |
| framework-validate reports missing `## Levels` | The file has level headings but no `## Levels` section marker -- add `## Levels` on its own line above the first `### [Level]` heading |
| framework-validate reports missing values | Add `## Company Values` section with `### [Value Name]` subsections |
| state-set fails | Fall back to telling the user to edit state.json manually |
| User wants to change one section only | Re-run that section, skip the rest (check current state first) |
| `mcp__scheduled-tasks__create_scheduled_task` fails | Render the §4.10 paste-block, continue with the next routine, summarize at the end |
| No calendar plugin found during 1:1 detection | Skip auto-detect, ask the user for day + time directly |
| Host is unsupported (not Claude Code or Codex) | Skip §4 entirely, tell the user routines run on demand instead |
| Host is Codex | Skip §4 (Phase 2), point to the Codex Automations UI |
| User on `permissions.defaultMode = "default"` | Warn at §4.7, default the prompt to "no", do not edit settings |
