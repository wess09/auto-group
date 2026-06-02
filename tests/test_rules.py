from app.models import AnswerRule
from app.models.entities import LogicMode, MatchMode
from app.services.rules import rule_matches


def test_contains_any_rule_matches_keyword() -> None:
    rule = AnswerRule(
        name="keywords",
        match_mode=MatchMode.contains,
        logic_mode=LogicMode.any,
        patterns=["答案A", "答案B"],
    )

    assert rule_matches(rule, "我的答案是答案b")


def test_exact_rule_requires_exact_answer() -> None:
    rule = AnswerRule(
        name="exact",
        match_mode=MatchMode.exact,
        logic_mode=LogicMode.any,
        patterns=["open sesame"],
    )

    assert rule_matches(rule, " Open Sesame ")
    assert not rule_matches(rule, "open sesame please")


def test_regex_all_rule() -> None:
    rule = AnswerRule(
        name="regex",
        match_mode=MatchMode.regex,
        logic_mode=LogicMode.all,
        patterns=[r"vip-\d+", r"2026"],
    )

    assert rule_matches(rule, "VIP-100 in 2026")
    assert not rule_matches(rule, "VIP-100")
