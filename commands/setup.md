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

If everything appears configured, tell the user: "Valor looks fully set up.
Want to reconfigure anything? (career framework / levels / integrations /
skip)"

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

## 4. Verification

Run the full check:

```bash
python3 ~/.valor/evidence_cli.py context
python3 ~/.valor/evidence_cli.py framework-slice
```

Present a summary:

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
```

Then suggest next steps:
- "Try: 'morning briefing' to see your first briefing"
- "Say 'valor quiet' anytime to suppress coaching for a conversation"
- "Say 'valor off' to disable coaching entirely (re-enable with 'valor on')"

## Fallbacks

| Scenario | Action |
|----------|--------|
| User can't find their career ladder | Offer the generic template, note they can customize later |
| User's ladder has different competency axes | Map to the closest of the five axes, explain the mapping |
| User doesn't know their level code | Help them identify it from the framework descriptions |
| framework-slice returns "Not found" | Level code mismatch -- check if heading uses a different format (e.g. "L3" vs "IC3") |
| state-set fails | Fall back to telling the user to edit state.json manually |
| User wants to change one section only | Re-run that section, skip the rest (check current state first) |
