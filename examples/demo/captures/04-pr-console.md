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
    Graph      3 actors · 3 containers · 8 components
    Quiz       6 questions, each answer checked against the diff
    Assemble   layout deterministic, 2 diffs inlined

A note on the quiz, because it's the part that decides whether this is useful: every
question is written from the diff and then checked back against it independently. A
candidate only survives if that second pass can defend one single answer from the code.
Anything ambiguous gets dropped rather than softened — so on a messier PR you get fewer
questions, not worse ones, and the count always follows the change instead of padding to
a round number.

Two examples of what does not survive here: "how many attempts does the client make?"
(it depends on the env flag, so both 3 and 5 are defensible) and anything about timeout
ownership (this diff doesn't change it, so there's nothing to test).

Console ready. It opens at System Context, and you can zoom Context → Inside →
Components → the real diff lines, flip Before ⇄ After, or play a request through the
system.

Caveats worth passing on: the box labels are generated, so on an unfamiliar PR they
sometimes want a wording tweak — say the word and I'll adjust them. And the gate is a
self-check, not a GitHub approval; the actual approval still happens in GitHub.

✓ Logged as evidence · pr_review_console · leadership
