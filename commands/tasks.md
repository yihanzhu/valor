# Valor Task Identifier

Helps the user find high-impact work opportunities by gathering available tasks from
Jira and GitHub, identifying competency gaps from the evidence store, and ranking
tasks by career impact and team need.

## Integration Check

Before gathering data, read `integrations` from `~/.valor/state.json`.
Skip sections for any integration set to `false` -- do not probe or print
a skip message.

| Integration | Sections skipped when `false` |
|-------------|-------------------------------|
| `jira`      | Jira tasks |
| `github`    | GitHub Issues, GitHub PRs to Review |

Evidence / competency gaps (section 2) are always available (local).

## 1. GATHER AVAILABLE WORK

### Jira

**Preferred: Atlassian MCP**

Check if Atlassian MCP tools are available. If `searchJiraIssuesUsingJql` exists:

1. Call `getAccessibleAtlassianResources` (plugin-atlassian-atlassian) to obtain `cloudId`.
2. Run these JQL searches with `searchJiraIssuesUsingJql` (use `maxResults: 50` for each):

   - **Unassigned tickets in user's projects:**
     ```
     project IN ($PROJECTS) AND assignee IS EMPTY AND status != Done ORDER BY priority DESC
     ```
   - **Stale tickets (no update in 2+ weeks):**
     ```
     project IN ($PROJECTS) AND updated <= -14d AND status != Done
     ```
   - **High priority items:**
     ```
     project IN ($PROJECTS) AND priority IN (Highest, High) AND status != Done
     ```

   Where `$PROJECTS` is the comma-separated list from `jira_projects` in
   state.json. If only one project, use `project = KEY` instead of `IN`.

**Project keys:** Read `jira_projects` from `~/.valor/state.json` (a list,
e.g. `["DAT", "DSAI"]`). If not set, fall back to `jira_default_project`
(single string). Use `project IN (...)` in JQL to search across all
listed projects. If the user mentions a different project key, add it
to the query.

**If Atlassian MCP is unavailable:** Skip the Jira section. If
`integrations.jira` is `true`, note: "Jira tools not found -- install an
Atlassian/Jira plugin, or set `integrations.jira` to `false` in state.json."

### GitHub Issues

If the user works in a GitHub repo context, run:

```bash
gh issue list --state open --limit 20
```

If `gh` is not authenticated, skip and note: "GitHub: `gh auth login`
needed, or set `integrations.github` to `false` in state.json."

### GitHub PRs to Review

Search for PRs the user could review. Run these in parallel:

```bash
# PRs explicitly requesting your review
gh search prs --review-requested=@me --state=open --json number,title,author,repository,url --limit 10

# Recent open PRs in adjacent repos
# Read github_owner from ~/.valor/state.json (no default -- skip if not set)
gh search prs --state=open --owner=$GITHUB_OWNER --sort=updated --json number,title,author,repository,url --limit 20
```

From the second query, filter for repos related to the user's domain. Use
`user_work_areas` from `~/.valor/state.json` and the user's known repos
(from evidence history, the current workspace, or nearby accessible repos)
to identify relevant PRs. Exclude the user's own PRs.

**Cross-team detection:** A PR is cross-team if the repo is outside the
user's usual repositories. Use `user_work_areas` from `~/.valor/state.json`
and evidence history to infer usual scope. Cross-team reviews carry
stronger career signal.

If `gh` is not authenticated, skip and note: "GitHub: `gh auth login`
needed, or set `integrations.github` to `false` in state.json."

## 2. CHECK COMPETENCY GAPS

Query the evidence store to identify which competencies have the fewest entries:

```bash
python3 ~/.valor/evidence_cli.py stats
```

Parse the output. The `by_competency` and `this_week` fields show counts per competency.
Competencies with low or zero counts are **gaps** — prioritize tasks that build these.

**Competency reference** (from `valor/src/competency.py`):

- `subject_matter`: Subject Matter Expertise — technical designs, clean code, ML concepts
- `industry_knowledge`: Industry Knowledge — tools, methods, algorithms
- `collaboration`: Internal Collaboration — cross-team alignment, task identification
- `autonomy_scope`: Autonomy & Scope — independent execution, design docs, PR reviews beyond scope
- `leadership`: Leadership — go-to expert, design decisions, identifying improvements

**If evidence store doesn't exist or `stats` fails:** Proceed without gap analysis.
Note: "Evidence store unavailable — run Valor briefings to populate competency data."

## 3. PRIORITIZE BY CAREER IMPACT

For each available task, assess:

| Factor | Higher Priority |
|--------|------------------|
| **Gap competency** | Task maps to a competency with low evidence |
| **Cross-team** | Involves another team (builds Collaboration/Leadership) |
| **Design/architecture** | Requires design doc or system design (builds Autonomy & Scope) |
| **Urgency** | High/Highest priority in Jira |
| **Staleness** | Stale ticket may indicate team need or overlooked work |

**Activity–competency mapping** (from `valor/src/competency.py` ACTIVITY_COMPETENCY_MAP):

- Design doc or complex system work → `autonomy_scope`, `subject_matter`
- Cross-team coordination or task for others → `collaboration`, `leadership`
- Standard implementation → `subject_matter`
- New tools/algorithms → `industry_knowledge`

Rank tasks using a mix of career impact and team need. Prefer tasks that fill gaps
and have higher Jira priority. De-duplicate when the same ticket appears in multiple
queries.

## 4. PRESENT RECOMMENDATIONS

Present **3–5** task recommendations plus **1–3** PR review opportunities:

```markdown
## High-Impact Work Opportunities

### Tasks

#### 1. [TICKET-123] [Title]
- **Career growth:** [Which competency, fills a gap?] E.g., "Builds Autonomy & Scope — you have 0 design docs this week."
- **Effort:** [S/M/L if inferable from labels, description, or type]
- **Cross-team:** [Yes/No — if applicable]
- **Why now:** [Urgency, staleness, or team need in 1 sentence]

#### 2. ...

### PRs Worth Reviewing

#### 1. [repo#NNN] [Title] by [author]
- **Career growth:** [Collaboration + Leadership if cross-team, Autonomy & Scope if own-team]
- **Cross-team:** [Yes/No]
- **Why review this:** [Relevance to your domain, touches shared systems, etc.]
- **Tip:** Say "review PR repo#NNN" to start a coached review.

#### 2. ...
```

Keep each recommendation concise. Surface the top reasons to pick each task
or review. PR review recommendations should explicitly link to the PR Review
Coach ("say 'review PR ...' to start a coached review").

## 5. OFFER TO HELP

After presenting recommendations, offer:

- "Want me to look at the ticket details?"
- "Should we draft a design doc for this?"
- "I can help you estimate the scope."
- "Want to review one of those PRs? I'll coach you through it."

Wait for the user to choose a task or PR before taking further action.

## 6. RECORD EVIDENCE WHEN USER PICKS A TASK

When the user explicitly chooses a task (e.g., "I'll take DS-456" or "let's work on that first"):

```bash
python3 ~/.valor/evidence_cli.py add \
    --activity task_identified \
    --competency collaboration \
    --statement "Proactively identified and picked up TICKET: TITLE" \
    --agent valor-task-identifier
```

Replace `TICKET` with the issue key (e.g., DS-456) and `TITLE` with the ticket title.
Use a truncated title if very long (e.g., first 60 chars).

## 7. FOLLOW-UP INTERACTIONS

If the user asks to dive deeper:

- **"Look at the ticket details"** — Use `getJiraIssue` (Atlassian MCP) with cloudId and issue key, or `gh issue view` for GitHub.
- **"Draft a design doc"** — Invoke `/valor-design-doc` to start a coached design doc.
- **"Help estimate scope"** — Break down the ticket into subtasks, identify dependencies, and suggest a rough S/M/L estimate with rationale.
- **"Review that PR"** or **"review PR repo#NNN"** — Invoke `/valor-pr-review` to start a coached review.

These follow-ups are part of the natural flow — no special trigger needed.
