import pytest

from src.competency import (
    Competency,
    ACTIVITY_COMPETENCY_MAP,
    AMBIENT_COACHING_TEMPLATES,
    coaching_tips_for_prs,
    coaching_tips_for_design_docs,
    gap_analysis,
)


# --- Competency enum ---

def test_competency_values():
    values = {c.value for c in Competency}
    assert values == {
        "subject_matter", "industry_knowledge", "collaboration",
        "autonomy_scope", "leadership",
    }


def test_competency_display_names_non_empty():
    for comp in Competency:
        assert isinstance(comp.display, str)
        assert len(comp.display) > 0


def test_competency_display_subject_matter():
    assert Competency.SUBJECT_MATTER.display == "Subject Matter Expertise"


def test_competency_target_description_non_empty():
    for comp in Competency:
        assert isinstance(comp.target_description, str)
        assert len(comp.target_description) > 10


def test_competency_is_str_subclass():
    assert isinstance(Competency.COLLABORATION, str)
    assert Competency.COLLABORATION == "collaboration"


def test_competency_from_value():
    comp = Competency("subject_matter")
    assert comp is Competency.SUBJECT_MATTER


def test_competency_invalid_value_raises():
    with pytest.raises(ValueError):
        Competency("not_a_valid_competency")


# --- ACTIVITY_COMPETENCY_MAP ---

def test_activity_competency_map_has_expected_keys():
    expected = {
        "pr_review_own_scope", "pr_review_cross_scope", "pr_review_cross_team",
        "design_doc_written", "ticket_completed", "code_written", "code_debugged",
        "mentoring_activity", "cross_team_alignment",
    }
    for key in expected:
        assert key in ACTIVITY_COMPETENCY_MAP, f"Missing key: {key}"


def test_activity_competency_map_values_are_lists_of_competency():
    for activity, comps in ACTIVITY_COMPETENCY_MAP.items():
        assert isinstance(comps, list), f"{activity} value is not a list"
        assert len(comps) > 0, f"{activity} list is empty"
        for c in comps:
            assert isinstance(c, Competency), f"{activity}: {c!r} is not a Competency"


def test_activity_competency_map_spot_check():
    assert Competency.AUTONOMY_SCOPE in ACTIVITY_COMPETENCY_MAP["pr_review_own_scope"]
    assert Competency.COLLABORATION in ACTIVITY_COMPETENCY_MAP["pr_review_cross_scope"]
    assert Competency.LEADERSHIP in ACTIVITY_COMPETENCY_MAP["mentoring_activity"]
    assert Competency.SUBJECT_MATTER in ACTIVITY_COMPETENCY_MAP["ticket_completed"]
    assert Competency.COLLABORATION in ACTIVITY_COMPETENCY_MAP["cross_team_alignment"]


# --- AMBIENT_COACHING_TEMPLATES ---

def test_ambient_coaching_templates_covers_ambient_activities():
    ambient_activities = {
        "code_written", "code_debugged", "investigation_completed",
        "documentation_updated", "cross_team_communication", "design_decision_made",
        "production_issue_resolved", "knowledge_shared", "process_improvement",
    }
    for activity in ambient_activities:
        assert activity in AMBIENT_COACHING_TEMPLATES, f"Missing template for: {activity}"


def test_ambient_coaching_templates_fields_non_empty():
    for activity, template in AMBIENT_COACHING_TEMPLATES.items():
        assert template.what_you_did, f"{activity}.what_you_did is empty"
        assert template.target_would_also, f"{activity}.target_would_also is empty"


# --- coaching_tips_for_prs ---

def test_coaching_tips_for_prs_below_target():
    tips = coaching_tips_for_prs(total_reviews=2, cross_scope_reviews=1, target_reviews_per_week=4)
    autonomy_tips = [t for t in tips if t.competency == Competency.AUTONOMY_SCOPE]
    assert len(autonomy_tips) >= 1
    assert any("2" in t.tip for t in autonomy_tips)


def test_coaching_tips_for_prs_at_target_no_autonomy_tip():
    tips = coaching_tips_for_prs(total_reviews=4, cross_scope_reviews=1, target_reviews_per_week=4)
    # At or above target: no "below target" tip
    below_target_tips = [t for t in tips if "target: 4" in t.tip]
    assert len(below_target_tips) == 0


def test_coaching_tips_for_prs_low_cross_scope_ratio():
    tips = coaching_tips_for_prs(total_reviews=4, cross_scope_reviews=0, target_reviews_per_week=4)
    collab_tips = [t for t in tips if t.competency == Competency.COLLABORATION]
    assert len(collab_tips) == 1
    assert "0%" in collab_tips[0].tip


def test_coaching_tips_for_prs_good_cross_scope_ratio():
    # 2/4 = 50% > 25% target — no collaboration tip
    tips = coaching_tips_for_prs(total_reviews=4, cross_scope_reviews=2, target_reviews_per_week=4)
    collab_tips = [t for t in tips if t.competency == Competency.COLLABORATION]
    assert len(collab_tips) == 0


def test_coaching_tips_for_prs_zero_reviews_no_division_error():
    # Must not raise ZeroDivisionError
    tips = coaching_tips_for_prs(total_reviews=0, cross_scope_reviews=0)
    assert len(tips) >= 1


def test_coaching_tips_for_prs_custom_targets():
    # 5 reviews >= target of 3 → no autonomy tip; 0/5=0% < 50% → collab tip
    tips = coaching_tips_for_prs(
        total_reviews=5,
        cross_scope_reviews=0,
        target_reviews_per_week=3,
        target_cross_scope_ratio=0.5,
    )
    below_target_tips = [t for t in tips if "target: 3" in t.tip]
    assert len(below_target_tips) == 0
    collab_tips = [t for t in tips if t.competency == Competency.COLLABORATION]
    assert len(collab_tips) == 1


# --- coaching_tips_for_design_docs ---

def test_coaching_tips_for_design_docs_complex_without_docs():
    tips = coaching_tips_for_design_docs(docs_this_sprint=1, complex_tickets_without_docs=2)
    autonomy_tips = [t for t in tips if t.competency == Competency.AUTONOMY_SCOPE]
    assert len(autonomy_tips) == 1
    assert "2 complex ticket" in autonomy_tips[0].tip


def test_coaching_tips_for_design_docs_zero_docs_this_sprint():
    tips = coaching_tips_for_design_docs(docs_this_sprint=0, complex_tickets_without_docs=0)
    subject_tips = [t for t in tips if t.competency == Competency.SUBJECT_MATTER]
    assert len(subject_tips) == 1


def test_coaching_tips_for_design_docs_both_issues():
    tips = coaching_tips_for_design_docs(docs_this_sprint=0, complex_tickets_without_docs=1)
    competencies = {t.competency for t in tips}
    assert Competency.AUTONOMY_SCOPE in competencies
    assert Competency.SUBJECT_MATTER in competencies


def test_coaching_tips_for_design_docs_no_issues():
    tips = coaching_tips_for_design_docs(docs_this_sprint=2, complex_tickets_without_docs=0)
    assert tips == []


# --- gap_analysis ---

def test_gap_analysis_all_competencies_missing():
    tips = gap_analysis({})
    assert len(tips) == len(list(Competency))
    gap_competencies = {t.competency for t in tips}
    assert gap_competencies == set(Competency)


def test_gap_analysis_all_present():
    counts = {comp: 3 for comp in Competency}
    tips = gap_analysis(counts)
    assert tips == []


def test_gap_analysis_partial_coverage():
    counts = {
        Competency.SUBJECT_MATTER: 2,
        Competency.COLLABORATION: 1,
    }
    tips = gap_analysis(counts)
    gap_competencies = {t.competency for t in tips}
    assert Competency.SUBJECT_MATTER not in gap_competencies
    assert Competency.COLLABORATION not in gap_competencies
    assert Competency.LEADERSHIP in gap_competencies
    assert Competency.AUTONOMY_SCOPE in gap_competencies
    assert Competency.INDUSTRY_KNOWLEDGE in gap_competencies


def test_gap_analysis_zero_count_treated_as_gap():
    counts = {comp: 0 for comp in Competency}
    tips = gap_analysis(counts)
    assert len(tips) == len(list(Competency))
