# Valor Design Doc Coach

Helps the user write technical design documents for complex tickets, with structured
options, trade-offs, career coaching, and evidence recording.

## Integration Check

Use `context.integrations` from the session-start context (already loaded).
If `integrations.jira` is `false`, skip all Jira lookups -- ask the user to
describe the problem directly instead. This command works fully without any
external integrations.

## 1. Gather Context

### Jira Ticket Lookup

Skip this section if `integrations.jira` is `false`.

**If the user mentions a Jira ticket (ID or key):**

1. Call `getAccessibleAtlassianResources` (plugin-atlassian-atlassian) to obtain `cloudId`.
2. Call `getJiraIssue` with `cloudId` and the issue key (e.g., `PROJ-123`).
3. Use the ticket's summary, description, acceptance criteria, and labels to inform the design doc.

**Fallback: Jira skills**

If Atlassian MCP is unavailable, check available slash commands for any
Jira-related command (look for commands matching `*jira*`). If found,
read and use it to fetch the ticket.

**If nothing is available:**

Ask the user to describe the problem, requirements, and constraints in their own words.
Proceed with the design doc structure using that input.

### Clarifying Questions

Before generating the full structure, ask about:

- **Constraints:** Timeline, team capacity, technical debt tolerance
- **Requirements:** Must-haves vs. nice-to-haves, success criteria
- **Scope:** In-scope vs. out-of-scope for this change
- **Dependencies:** Systems, teams, or migrations involved

If the user provides enough context upfront, skip redundant questions and proceed.

## 2. Generate Design Doc Structure

Produce a design document with the following structure. Use the ticket content and
user input to populate each section.

```markdown
# Design Doc: [Title]

## Problem Statement
[1-2 paragraphs: What problem are we solving? Why now?]

## Background / Context
[What exists today? Why is change needed? Relevant system context.]

## Goals and Non-Goals
**Goals:**
- [Goal 1]
- [Goal 2]

**Non-Goals:**
- [Out of scope item 1]
- [Out of scope item 2]

## Approach Options

### Option A: [Name]
**Description:** [1-2 paragraphs]
**Pros:** [Bullet list]
**Cons:** [Bullet list]
**Effort:** [Rough estimate: e.g., 2-3 weeks, 1 sprint]
**Risks:** [Low / Medium / High + brief note]

### Option B: [Name]
[Same structure]

### Option C: [Name] (if applicable)
[Same structure]

## Recommended Approach
[Which option and why. Justify with trade-offs, risk tolerance, and team context.]

## Testing Strategy
[Unit tests, integration tests, canary, monitoring, rollback checks.]

## Rollout Plan (if applicable)
[Phases, feature flags, gradual rollout, dependencies.]

## Open Questions
- [Question 1]
- [Question 2]
```

**Requirements:**

- Provide **2-3 approach options** with distinct trade-offs. Do not default to a single solution.
- Each option must have pros, cons, effort estimate, and risk assessment.
- The recommended approach must be justified against the alternatives.

## 3. Career Coaching

After presenting the structure (or when appropriate), include a brief coaching note:

> **Career note:** Writing this design doc builds **Autonomy & Scope** evidence. A good design doc shows you can think through options independently. At your target level, presenting trade-offs (not just one solution) demonstrates design thinking. Share this doc with your team for discussion.

**Key points to reinforce:**

- Autonomy and scope: the doc demonstrates independent analysis of options.
- At the target level, presenting trade-offs (not just one recommendation) is expected.
- The doc should be shareable for team discussion and alignment.

## 4. Iterate

After presenting the structure, offer to:

- **Flesh out any section** -- expand Problem Statement, Background, or any option in detail.
- **Add more options** -- if the user wants additional alternatives.
- **Refine the recommendation** -- adjust the recommended approach with new constraints or preferences.
- **Format for Google Docs or Confluence** -- restructure for copy-paste or Confluence-style formatting.

## 5. Record Evidence

When the user has a design doc structure (or a section they consider "done" enough to count),
record evidence for both competencies. Use the Valor evidence CLI:

```bash
python3 ~/.valor/evidence_cli.py add \
  --activity design_doc_written \
  --competency autonomy_scope \
  --statement "Wrote design doc for [TICKET]: [TITLE]" \
  --agent valor-design-doc-coach

python3 ~/.valor/evidence_cli.py add \
  --activity design_doc_written \
  --competency subject_matter \
  --statement "Wrote design doc for [TICKET]: [TITLE]" \
  --agent valor-design-doc-coach
```

Replace `[TICKET]` and `[TITLE]` with the actual ticket ID (e.g., `PROJ-123`) and short title.

**Competency mapping** (from `valor/src/evidence_cli.py`):

- `design_doc_written` -> `autonomy_scope`, `subject_matter`

**When to record:**

- After the user confirms the design doc structure is complete, or
- After fleshing out the core sections (Problem, Options, Recommendation) to a shareable state.

Do not record multiple times for minor edits. One recording per distinct design doc is sufficient.

## 6. Fallbacks

| Scenario | Action |
|----------|--------|
| No Jira ticket mentioned | Ask user to describe the problem and constraints. Proceed with that input. |
| Atlassian MCP unavailable | Proceed without ticket data. Ask for problem statement and context. |
| User provides minimal context | Ask 2-3 clarifying questions, then generate. Don't block on exhaustive answers. |
| Evidence CLI fails | Continue with the design doc. Note: "Evidence recording unavailable." |
