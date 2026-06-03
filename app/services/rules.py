import re

from sqlmodel import Session, col, select

from app.models import AnswerRule
from app.models.entities import LogicMode, MatchMode


def match_one(pattern: str, answer: str, mode: MatchMode) -> bool:
    pattern = pattern.strip()
    if not pattern:
        return False
    if mode == MatchMode.contains:
        return pattern.casefold() in answer.casefold()
    if mode == MatchMode.exact:
        return pattern.casefold() == answer.strip().casefold()
    if mode == MatchMode.regex:
        try:
            return re.search(pattern, answer, flags=re.IGNORECASE) is not None
        except re.error:
            return False
    return False


def rule_matches(rule: AnswerRule, answer: str) -> bool:
    patterns = [pattern for pattern in rule.patterns if pattern.strip()]
    if not patterns:
        return False
    results = [match_one(pattern, answer, rule.match_mode) for pattern in patterns]
    if rule.logic_mode == LogicMode.all:
        return all(results)
    return any(results)


def find_matching_rule(session: Session, group_id: int, answer: str) -> AnswerRule | None:
    rules = session.exec(
        select(AnswerRule)
        .where(AnswerRule.enabled == True)  # noqa: E712
        .order_by(col(AnswerRule.group_id).desc())
    ).all()
    for rule in rules:
        if rule.group_id is not None and rule.group_id != group_id:
            continue
        if rule_matches(rule, answer):
            return rule
    return None
