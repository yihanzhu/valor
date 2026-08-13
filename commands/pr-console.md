# Valor PR Review Console

<!-- valor:integrations github=required jira=none calendar=none news=none -->

Turns a pull request into an **interactive C4 review console** — a plain-English,
zoomable diagram (System Context → Containers → Components → real code) with a
Before ⇄ After toggle, a request-flow animation, and a **coverage-driven mastery
quiz** whose answers are independently verified against the diff. The reviewer
must ace the quiz (all correct) to be "approval-ready", so approving means they
actually understand the change. Published as a private Artifact.

Fully automatic: the C4 labels, groupings, before/after, and quiz are generated
from the diff — no hand-editing.

## Integration Check

Use `context.integrations` from the session-start context. This command
**requires** `integrations.github == true`. If false, tell the user to set it in
`~/.valor/state.json` and run `gh auth login`, and stop.

## Prerequisites

- User provides a PR (number or URL), e.g. "build a review console for #123".
- `gh` CLI authenticated.
- The **Workflow** tool and the **Artifact** tool must be available in this
  session (this command orchestrates a generator workflow and publishes an
  artifact). If either is missing, tell the user and stop.
- Assets (installed with this command): `~/.valor/pr-console/template.html`
  (renderer), `generate.js` (generator workflow), `assemble.py` (layout+inject).

## 1. Gather the PR

Pick a working dir and fetch the PR. Determine `OWNER/REPO` from the URL or ask.

```bash
WORK=$(mktemp -d); mkdir -p "$WORK/pr_context" "$WORK/diff_by_file"; echo "$WORK"
gh pr view NUMBER --repo OWNER/REPO --json number,title,body,headRefOid,files > "$WORK/pr_meta.json"
gh pr diff NUMBER --repo OWNER/REPO > "$WORK/pr_context/pr_diff.txt"
```

Split the diff into per-file slices the generator/assembler expect:

```bash
python3 - "$WORK" <<'PY'
import re, os, sys
work = sys.argv[1]
raw = open(os.path.join(work, "pr_context", "pr_diff.txt")).read()
for p in re.split(r"(?m)^(?=diff --git )", raw):
    m = re.search(r"^diff --git a/\S+ b/(\S+)", p)
    if not m:
        continue
    open(os.path.join(work, "diff_by_file", m.group(1).replace("/", "__") + ".diff"), "w").write(p)
print("split ok")
PY
```

From `pr_meta.json`, build the list of **changed production files** — the
`.files[].path` values, EXCLUDING tests (paths containing `/tests/`, starting
with `tests/`, `__tests__`, or ending `.test.*`/`_test.*`/`.spec.*`). Tests
aren't drawn on the diagram. Keep the PR `title`, `number`, and `body` (as
`prDesc`).

## 2. Generate the logical graph + verified quiz

Run the generator workflow. Pass the working dir and the production file list:

```
Workflow({
  scriptPath: "~/.valor/pr-console/generate.js",   // expand ~ to the real home
  args: { base: "<WORK>", title: "<PR title>", number: <PR number>,
          prDesc: "<PR body>", files: ["services/.../a.py", ...] }
})
```

It runs in the background; wait for the completion notification. Then read the
workflow's **result** object (the `result` field of the task output file) and
save it as the generator output:

```bash
python3 - "<task_output_file>" "$WORK/gen.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
json.dump(d.get("result", d), open(sys.argv[2], "w"), indent=2, ensure_ascii=False)
print("gen.json written")
PY
```

If `gen.json._dropped` is non-empty, mention how many quiz candidates were
dropped in verification (and why) when you report back — that's the answer
accuracy guard working.

## 3. Assemble the console

```bash
python3 ~/.valor/pr-console/assemble.py \
  --gen "$WORK/gen.json" \
  --diffdir "$WORK/diff_by_file" \
  --out "$WORK/pr_console.html"
```

`assemble.py` lays out the graph deterministically (row-major grid — boxes never
overlap), pulls each component's real diff from `diff_by_file/`, and injects
everything into the template. If it warns about a leftover placeholder, stop and
report — the generator output was malformed.

## 4. Publish

Publish `$WORK/pr_console.html` with the **Artifact** tool (favicon 🕹️, a
one-line description naming the PR). Return the URL to the user. If they asked to
update an existing console, pass that artifact's `url`.

## 5. Record Evidence

```bash
python3 ~/.valor/evidence_cli.py add \
  --activity pr_review_console \
  --competency leadership \
  --statement "Built an interactive C4 review console + verified mastery quiz for PR #NUMBER: TITLE" \
  --agent valor-pr-console
```

Valid `--competency` values are: `subject_matter`, `industry_knowledge`,
`collaboration`, `autonomy_scope`, `leadership`. Building reviewer-onboarding
tooling and raising the review bar is `leadership`; for a cross-team PR use
`collaboration` instead. If the evidence CLI fails, log a note but don't block.

## 6. Coaching Note

Add a brief Valor footer (per `~/.valor/coaching-ref.md`): making a PR
understandable to any reviewer — and gating approval on understanding — is a
force-multiplier behavior (target-level Leadership / Knowledge Sharing).

## Honest caveats to pass along

- The diagram labels/groupings are LLM-generated; on the first run for an
  unfamiliar PR they may need a light wording tweak. Offer to adjust.
- The quiz gate is a **self-check**, not a GitHub approval — the reviewer still
  records the real approval in GitHub.
- Answers are independently verified against the diff, and unverifiable/ambiguous
  candidates are dropped, so the surviving quiz is trustworthy.

## Flow Summary

1. Fetch PR meta + diff; split per-file; list production (non-test) files.
2. Run `generate.js` (analyze → C4 graph → coverage-driven quiz → verify answers).
3. `assemble.py` lays out + injects into `template.html`.
4. Publish as an Artifact; return the link.
5. Record evidence; add a coaching note.
