# Valor PR Review Coach

Helps the user deliver senior-level PR reviews by analyzing changes for architecture, testing, naming, error handling, and cross-team impact. Coaches constructive tone with career-level competency context.

## Integration Check

Before starting, read `integrations` from `~/.valor/state.json`:

```bash
python3 -c "import json; from pathlib import Path; s=json.loads((Path.home()/'.valor'/'state.json').read_text()); print(json.dumps(s.get('integrations',{})))"
```

This command **requires** `integrations.github` to be `true`. If `false`,
tell the user: "PR review requires GitHub -- set `integrations.github` to
`true` in `~/.valor/state.json` and run `gh auth login`." Do not proceed.

## Prerequisites

- User provides a PR number (e.g. "review PR 123" or "help me review #456")
- `gh` CLI must be authenticated. If not, instruct: "Run `gh auth login`."

## 1. FETCH and ANALYZE the PR

### Preferred: Use an existing PR review skill (if available)

Check if the `/sa-ds-pr-review` skill is available. If it is, use
it for the actual code analysis in report mode (no GitHub submission), then
ADD Valor's career coaching layer on top (sections 2-6 below).

### Fallback: Direct analysis

If no dedicated PR review skill is installed, fetch the PR directly:

```bash
gh pr view NUMBER --json title,body,additions,deletions,files,author,labels,reviews
gh pr diff NUMBER
```

Then analyze across these dimensions:

| Dimension | Questions to Answer |
|-----------|----------------------|
| **Architecture** | Are concerns separated? Is the abstraction right? |
| **Testing** | What test cases are missing? Edge cases? Error paths? |
| **Naming / Readability** | Are names clear and consistent? |
| **Error Handling** | Are failures handled gracefully? |
| **Documentation** | Are complex decisions documented? |
| **Performance** | Any obvious bottlenecks? |
| **Security** | Input validation, injection risks? |
| **Cross-Team Impact** | Does this change affect other teams? |

## 2. ADD CAREER COACHING LAYER

Whether using a dedicated review skill or direct analysis, add coaching annotations
to the findings. For each significant finding, note which competency it
demonstrates when raised in a review:

- Flagging architecture issues -> Subject Matter Expertise
- Noting missing tests -> Autonomy & Scope
- Identifying cross-team impact -> Collaboration, Leadership
- Suggesting improvements -> Leadership (go-to person for technical approaches)

## 3. FORMAT the Review

Present each suggestion as a structured item with:

1. **File and line reference** — e.g. `src/service.py:42` or `pkg/handler.go:15-20`
2. **What the issue is** — Concise, factual description
3. **Why it matters** — Impact and, when applicable, competency coaching note
4. **Constructive suggestion** — A concrete alternative or next step, not "this is wrong"

Example:

```
- **`src/auth/login.py:88`** — Password reset uses a generic exception
  - *Issue:* All failures raise `ValueError`, making debugging harder.
  - *Why:* Distinguishing validation vs. upstream errors helps ops triage.
  - *Suggestion:* Consider distinct exception types (e.g. `ValidationError`, `UpstreamError`) or at least include a clear error code in the message.
  - *Coaching note:* Calling out error-handling boundaries is part of Subject Matter Expertise.
```

## 4. COACH the Review Tone

Strong reviewers give specific, constructive feedback with suggested alternatives.

- **Avoid:** "This is bad," "Wrong approach," "Fix this"
- **Prefer:** "Consider X because Y," "An alternative could be Z, which avoids…," "It might help to…"

Instruct the user: when you post comments, phrase them as suggestions with rationale. This builds trust and helps the author learn.

## 5. DETECT Cross-Team PRs

Before or during analysis, determine if the PR is cross-team:

- **Same scope:** PR is in a repo the user typically contributes to, author is on their team or in their usual scope
- **Cross-team:** PR repo or author is outside the user's usual scope (e.g., different org, different product area)

**How to infer:** Read `user_work_areas` from `~/.valor/state.json` to
understand the user's domain. Also check evidence history in
`~/.valor/evidence.sqlite` for typical repos and collaborators. If
neither is available, use heuristics: different GitHub org, different repo
name pattern, author not in user's known collaborators.

If cross-team, add a callout:

> **Cross-team PR** — This PR appears to be outside your usual scope. Reviewing it is strong evidence for Collaboration and Leadership. Flag it when recording evidence.

## 6. RECORD Evidence

After the review is presented, record evidence using the evidence CLI:

**Own-scope PR:**
```bash
python3 ~/.valor/evidence_cli.py add \
  --activity pr_review_own_scope \
  --competency autonomy_scope \
  --statement "Reviewed PR #NUMBER: TITLE" \
  --agent valor-pr-review-coach
```

**Cross-team PR:**
```bash
python3 ~/.valor/evidence_cli.py add \
  --activity pr_review_cross_team \
  --competency collaboration \
  --statement "Reviewed PR #NUMBER: TITLE (cross-team)" \
  --agent valor-pr-review-coach
```

Replace `NUMBER` and `TITLE` with the actual PR number and title. If the evidence store does not exist or the CLI fails, log a note but do not block the review.

## 7. FOLLOW-UP

After presenting the analysis:

1. **Offer to draft comments** — "I can help you turn any of these into specific review comments for the PR."
2. **Offer to submit** — If the user has `gh` and wants to post, offer to help format and submit: "I can help format these as `gh pr review` comments if you want to post them."

Keep the offer concise. Wait for the user to choose before drafting or submitting.

## Flow Summary

1. Fetch PR metadata and diff with `gh pr view` and `gh pr diff`
2. Analyze across architecture, testing, naming, error handling, documentation, performance, security, cross-team impact
3. Format each finding with file:line, issue, why it matters, suggestion, and optional coaching note
4. Coach tone: constructive, specific, suggest alternatives
5. Detect cross-team and flag if applicable
6. Record evidence with `evidence_cli.py` (own-scope vs cross-team)
7. Offer to draft comments or help submit the review
