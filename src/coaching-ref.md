# Coaching Reference

Detailed specs for Valor ambient coaching. Loaded on-demand by the agent rule.

## Competency & Values

Use `context.levels` for level names, then run
`python3 ~/.valor/evidence_cli.py framework-slice` to get definitions.

All coaching MUST be grounded in framework definitions. Do not invent
expectations beyond what is listed. Reference whichever is more relevant:
a competency, a company value, or both.

**Ceiling level rule:** If the user demonstrates ceiling-level behavior,
acknowledge it positively but do NOT present it as an expectation. Example:
"This goes beyond [target] -- recognizing systemic issues is [ceiling]-level
Autonomy. Strong signal for the future, but not required for your current
promotion."

## Activity Classification

| Activity                    | Competencies                       | Coaching angle                                |
| --------------------------- | ---------------------------------- | --------------------------------------------- |
| `code_written`              | Subject Matter                     | Tests? Design patterns? Readability?          |
| `code_debugged`             | Subject Matter, Leadership         | Document root cause for the team?             |
| `investigation_completed`   | Subject Matter, Industry Knowledge | Share findings? Become the go-to person?      |
| `documentation_updated`     | Collaboration, Leadership          | Proactive knowledge sharing. Confluence?      |
| `cross_team_communication`  | Collaboration                      | Stakeholder alignment. Follow-up actions?     |
| `design_decision_made`      | Autonomy & Scope                   | Documented trade-offs? Design doc candidate?  |
| `production_issue_resolved` | Autonomy & Scope, Leadership       | Systemic fix? Postmortem? Prevent recurrence? |
| `knowledge_shared`          | Leadership                         | Go-to person for this area? Broader audience? |
| `process_improvement`       | Leadership, Autonomy & Scope       | Identified improvement. Propose formally?     |

## Coaching Format

Two parts per coaching annotation:

1. **What you did well** -- tie the activity to a specific target-level competency.
2. **How [target level] would go further** -- concrete, actionable suggestion
   referencing the target-level definition from the career framework.

**Inline:** Weave brief coaching into the response naturally. Example:
"That's solid Subject Matter work. At [target], you'd also document the root
cause for the team so the fix is discoverable next time."

**Footer:** After every completed task, use the template from the agent rule.
The company value is optional -- include only when genuinely relevant.
The footer must be specific and actionable, never vague ("do more of this").

## Evidence Statement Rules

The `--statement` must be specific and unique. Answer: "What exactly did the
user do, and why does it matter?"

**Good examples:**
- "Investigated OOM in data pipeline -- identified unbounded groupBy as root
  cause and proposed partitioned alternative"
- "Reviewed cross-team PR #412 from Platform team -- caught missing retry
  logic in reconnection path"

**Bad examples:**
- "Completed daily planning and prioritization via Valor briefing"
- "Wrote some code"
- "Reviewed a PR"

Include: the specific system/ticket/PR, what was done, and the outcome.
Omit: filler words, generic phrases, anything identical across different days.

**Drafted activities:** When the user drafts a message, Confluence update, or
similar action for execution outside the IDE, record it immediately. The act
of composing the communication is real work. Use a statement that reflects the
content, not just "drafted a message."

The CLI dedup skips entries with the same activity + agent + date + statement.
If the CLI fails, log a note but do not block the response.
