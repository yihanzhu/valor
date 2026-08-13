id: pr-console
command: /valor-pr-console
phrase: build a review console for #418
label: PR review console
act: A week
blurb: Turns the diff into a zoomable C4 walkthrough plus a quiz whose answers are verified against the diff.
console: pr-console.html
---
Building the review console for #418 (example-org/checkout-service).

    Fetch      3 changed files, 1 excluded as tests
    Analyze    net/transport.py, api/payments_client.py
    Graph      2 actors · 3 containers · 5 components
    Quiz       8 candidates generated, 2 dropped in verification
    Assemble   layout deterministic, 3 diffs inlined

Two quiz candidates were dropped because an independent check against the diff couldn't defend a
single answer:

  - "How many attempts does the client make?" — depends on the env flag, so both 3 and 5 are correct
  - "Which layer owns the timeout?" — the diff doesn't change timeout ownership; nothing to test

That leaves 6 verified questions. The reviewer has to get all 6 right to be marked approval-ready.

Console ready. It opens at System Context, and you can zoom Context → Inside → Components → the real
diff lines, flip Before ⇄ After, or play a request through the system.

Caveats worth passing on: the box labels are generated, so on an unfamiliar PR they sometimes want a
wording tweak — say the word and I'll adjust them. And the gate is a self-check, not a GitHub
approval; the actual approval still happens in GitHub.

✓ Logged as evidence · pr_review_console · leadership
