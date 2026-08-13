id: console-gate
command: (follow-up)
phrase: what happens if the reviewer gets one wrong?
label: Ask about the gate
act: A week
blurb: The quiz is all-or-nothing on purpose — and it can't approve anything for you.
---
They don't pass. The gate wants all six, not a majority.

When they miss one, the console shows every question they got wrong, what they answered, the correct
answer, and why the tempting wrong answer is wrong — then sends them back into the diagram to dig into
that specific piece. They can retake it as many times as they like.

That sounds harsh for a quiz, and it's deliberate. A 4-of-6 reviewer is someone who understood the
backoff curve and missed that captures silently stopped retrying — which is exactly the finding that
should block this PR. Partial credit would let the most important question be the one they skipped.

Two honest limits worth repeating to anyone you hand this to:

**It is a self-check, not an approval.** Acing it flips a label in the page. The real approval still
happens in GitHub, by a human who chooses to give it.

**The questions come from the diff, not from a rulebook.** Six survived here because an independent
pass could defend a single answer from the code. Two didn't and were dropped. On a PR with more
ambiguity you'd get fewer questions, not worse ones — the count follows the change, and it never pads
to a round number.

The console for this PR is embedded further down this page. Try the gate yourself: get one wrong on
purpose and see what it hands back.
