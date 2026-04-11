"""Competency framework for career coaching.

Defines the five competency categories and provides helpers for mapping
activities to competencies and generating coaching annotations. Level
definitions are loaded from ~/.valor/career_framework.md at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Competency(str, Enum):
    SUBJECT_MATTER = "subject_matter"
    INDUSTRY_KNOWLEDGE = "industry_knowledge"
    COLLABORATION = "collaboration"
    AUTONOMY_SCOPE = "autonomy_scope"
    LEADERSHIP = "leadership"

    @property
    def display(self) -> str:
        return _DISPLAY[self]

    @property
    def target_description(self) -> str:
        return _TARGET_DESCRIPTIONS[self]


_DISPLAY = {
    Competency.SUBJECT_MATTER: "Subject Matter Expertise",
    Competency.INDUSTRY_KNOWLEDGE: "Industry Knowledge",
    Competency.COLLABORATION: "Internal Collaboration",
    Competency.AUTONOMY_SCOPE: "Autonomy & Scope",
    Competency.LEADERSHIP: "Leadership",
}

_TARGET_DESCRIPTIONS = {
    Competency.SUBJECT_MATTER: (
        "Converts business-facing requirements into technical designs, "
        "then writes clean, maintainable, and well-tested code. "
        "Understands ML concepts when relevant to task domain."
    ),
    Competency.INDUSTRY_KNOWLEDGE: (
        "Strong understanding of technologies used in technical systems. "
        "Aware of new industry methods, tools, or algorithms relevant "
        "to their technical systems."
    ),
    Competency.COLLABORATION: (
        "Proactively gathers information on project context from within "
        "the team. Identifies tasks for themselves and others. "
        "Proactively aligns with relevant internal technical teams on "
        "technical plans and requirements."
    ),
    Competency.AUTONOMY_SCOPE: (
        "Executes moderate-complexity tasks independently. "
        "Designs moderate to complex systems with guidance. "
        "Mostly self-directed and guided by project requirements. "
        "Actively participates in PR reviews including ones not "
        "immediately related to their tasks. Creates and contributes "
        "to design docs. Takes responsibility for operational health, "
        "monitoring, and reliability of production systems."
    ),
    Competency.LEADERSHIP: (
        "Go-to person for team members for clarifying and standardizing "
        "technical approaches. Subject matter expert on portions of code "
        "architecture. Identifies significant improvements for code on "
        "own team. Contributes to broader project team discussions and "
        "design decisions."
    ),
}


@dataclass
class CoachingTip:
    activity: str
    competency: Competency
    tip: str


ACTIVITY_COMPETENCY_MAP: dict[str, list[Competency]] = {
    # Agent-triggered activities (sections 1-5)
    "pr_review_own_scope": [Competency.AUTONOMY_SCOPE],
    # cross_scope: PR in a repo outside your usual scope (broader visibility)
    "pr_review_cross_scope": [Competency.COLLABORATION, Competency.AUTONOMY_SCOPE],
    # cross_team: PR from a different team entirely (stronger leadership signal)
    "pr_review_cross_team": [Competency.COLLABORATION, Competency.LEADERSHIP],
    "design_doc_written": [Competency.AUTONOMY_SCOPE, Competency.SUBJECT_MATTER],
    "ticket_completed": [Competency.SUBJECT_MATTER],
    "complex_ticket_completed": [Competency.SUBJECT_MATTER, Competency.AUTONOMY_SCOPE],
    "meeting_proactive_suggestion": [Competency.COLLABORATION, Competency.LEADERSHIP],
    "task_identified_for_others": [Competency.COLLABORATION, Competency.LEADERSHIP],
    "tech_debt_proposed": [Competency.AUTONOMY_SCOPE, Competency.LEADERSHIP],
    "mentoring_activity": [Competency.LEADERSHIP],
    "cross_team_alignment": [Competency.COLLABORATION],
    "operational_health_improvement": [Competency.AUTONOMY_SCOPE],
    # Ambient coaching activities (section 6)
    "code_written": [Competency.SUBJECT_MATTER],
    "code_debugged": [Competency.SUBJECT_MATTER, Competency.LEADERSHIP],
    "investigation_completed": [Competency.SUBJECT_MATTER, Competency.INDUSTRY_KNOWLEDGE],
    "documentation_updated": [Competency.COLLABORATION, Competency.LEADERSHIP],
    "cross_team_communication": [Competency.COLLABORATION],
    "design_decision_made": [Competency.AUTONOMY_SCOPE],
    "production_issue_resolved": [Competency.AUTONOMY_SCOPE, Competency.LEADERSHIP],
    "knowledge_shared": [Competency.LEADERSHIP],
    "process_improvement": [Competency.LEADERSHIP, Competency.AUTONOMY_SCOPE],
}


@dataclass
class AmbientCoachingTemplate:
    what_you_did: str
    target_would_also: str


AMBIENT_COACHING_TEMPLATES: dict[str, AmbientCoachingTemplate] = {
    "code_written": AmbientCoachingTemplate(
        what_you_did="Wrote working code for the task.",
        target_would_also=(
            "Add tests covering edge cases, write a brief docstring explaining "
            "the 'why', and ensure a teammate could understand it without asking."
        ),
    ),
    "code_debugged": AmbientCoachingTemplate(
        what_you_did="Investigated and fixed a bug.",
        target_would_also=(
            "Document the root cause in the ticket or a team channel so the "
            "fix is discoverable. If it's a pattern, propose a systemic fix."
        ),
    ),
    "investigation_completed": AmbientCoachingTemplate(
        what_you_did="Completed a technical investigation.",
        target_would_also=(
            "Write up findings in Confluence or a reference doc. This builds "
            "your reputation as the go-to person for this area."
        ),
    ),
    "documentation_updated": AmbientCoachingTemplate(
        what_you_did="Proactively updated documentation.",
        target_would_also=(
            "Share the doc with stakeholders who weren't present and tag "
            "affected teams. Proactive sharing is what elevates "
            "collaboration to the next level."
        ),
    ),
    "cross_team_communication": AmbientCoachingTemplate(
        what_you_did="Aligned with another team on technical plans.",
        target_would_also=(
            "Follow up with a written summary of agreements and next steps. "
            "Identify tasks for both sides and track them."
        ),
    ),
    "design_decision_made": AmbientCoachingTemplate(
        what_you_did="Made a technical design decision.",
        target_would_also=(
            "Write a short design doc with 2-3 options and trade-offs before "
            "implementing. Documenting design thinking demonstrates target-level "
            "autonomy even for moderate-complexity tasks."
        ),
    ),
    "production_issue_resolved": AmbientCoachingTemplate(
        what_you_did="Resolved a production issue.",
        target_would_also=(
            "Write a brief postmortem or propose a systemic fix to prevent "
            "recurrence. Owning operational health (not just incident response) "
            "is a target-level expectation."
        ),
    ),
    "knowledge_shared": AmbientCoachingTemplate(
        what_you_did="Shared technical knowledge with the team.",
        target_would_also=(
            "Widen the audience -- a team demo, Confluence page, or Slack "
            "write-up reaches people who weren't in the conversation."
        ),
    ),
    "process_improvement": AmbientCoachingTemplate(
        what_you_did="Identified a process improvement.",
        target_would_also=(
            "Formalize the proposal in a ticket or doc so it can be tracked, "
            "prioritized, and attributed to you."
        ),
    ),
}


def coaching_tips_for_prs(
    total_reviews: int,
    cross_scope_reviews: int,
    target_reviews_per_week: int = 4,
    target_cross_scope_ratio: float = 0.25,
) -> list[CoachingTip]:
    tips: list[CoachingTip] = []
    if total_reviews < target_reviews_per_week:
        tips.append(CoachingTip(
            activity="pr_review",
            competency=Competency.AUTONOMY_SCOPE,
            tip=(
                f"You've done {total_reviews} reviews this week "
                f"(target: {target_reviews_per_week}). "
                "Actively reviewing PRs -- including ones not directly related "
                "to your tasks -- demonstrates target-level scope."
            ),
        ))
    ratio = cross_scope_reviews / max(total_reviews, 1)
    if ratio < target_cross_scope_ratio:
        tips.append(CoachingTip(
            activity="pr_review_cross_scope",
            competency=Competency.COLLABORATION,
            tip=(
                f"Cross-scope review ratio: {ratio:.0%} "
                f"(target: {target_cross_scope_ratio:.0%}). "
                "Reviewing code outside your direct scope builds broader "
                "expertise and demonstrates target-level collaboration."
            ),
        ))
    return tips


def coaching_tips_for_design_docs(
    docs_this_sprint: int,
    complex_tickets_without_docs: int,
) -> list[CoachingTip]:
    tips: list[CoachingTip] = []
    if complex_tickets_without_docs > 0:
        tips.append(CoachingTip(
            activity="design_doc",
            competency=Competency.AUTONOMY_SCOPE,
            tip=(
                f"{complex_tickets_without_docs} complex ticket(s) started "
                "without a design doc. Writing a short doc with 2-3 approach "
                "options demonstrates target-level design thinking."
            ),
        ))
    if docs_this_sprint == 0:
        tips.append(CoachingTip(
            activity="design_doc",
            competency=Competency.SUBJECT_MATTER,
            tip=(
                "No design docs written this sprint. Converting business "
                "requirements into technical designs is a core target-level competency."
            ),
        ))
    return tips


def gap_analysis(evidence_counts: dict[Competency, int]) -> list[CoachingTip]:
    """Identify competency gaps from weekly evidence counts."""
    tips: list[CoachingTip] = []
    for comp in Competency:
        count = evidence_counts.get(comp, 0)
        if count == 0:
            tips.append(CoachingTip(
                activity="gap",
                competency=comp,
                tip=f"No {comp.display} evidence this week. {comp.target_description}",
            ))
    return tips
