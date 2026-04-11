# Agent Team Templates for Valor

Ready-to-use prompts for Claude Code Agent Teams. These templates assume the
usual planner/coder/tester/reviewer team shape, but they can be adjusted for
your own local setup.

## Template A: Phase 3 -- Background Daemon

```text
Create a team to build the Phase 3 background daemon (see ROADMAP.md).

PLANNER: design the daemon architecture (monitor.py, notify.py,
sources/, launchd plist). Evaluate notification channel options from
ROADMAP.md. Read existing src/ to understand the evidence store.

CODER-1 owns daemon/monitor.py + daemon/sources/*.
CODER-2 owns daemon/notify.py + daemon/*.plist.
TESTER owns tests/.

Constraint: stdlib only for production code. pytest allowed for tests.
```

## Template B: Add Tests to Existing Code

```text
Create a team with 1 PLANNER and 2 TESTERs.

PLANNER: analyze src/ and identify what needs tests. Create a test plan.

TESTER-1 owns tests/test_evidence_store.py and tests/test_competency.py.
TESTER-2 owns tests/test_evidence_cli.py and tests/conftest.py.
```

## Template C: New Feature

```text
Create a team to add [feature description].

PLANNER: design the approach, identify which files to create/modify.
CODER: implement in [target directory].
TESTER: write tests in tests/.
REVIEWER: review after implementation.
```

## Template D: Investigation / Debug

```text
Create a team to investigate [problem description].

Use 2 PLANNERs with competing hypotheses:
PLANNER-1: investigate [hypothesis A].
PLANNER-2: investigate [hypothesis B].

Share findings and converge on the root cause.
```

## Template E: Quick Fix

For small tasks that don't need a full team:

```text
Create a team with 1 CODER and 1 TESTER.
CODER: fix [issue] in [file].
TESTER: add a regression test in tests/.
```
