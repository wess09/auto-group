"""Normalize OneBot notice text, including existing Python-repr snapshots."""

import ast
import json


def content_text(value) -> str:
    if isinstance(value, str) and value.lstrip().startswith("{"):
        for parse in (json.loads, ast.literal_eval):
            try:
                parsed = parse(value)
                if isinstance(parsed, dict) and isinstance(parsed.get("text"), str):
                    return parsed["text"]
            except (ValueError, SyntaxError, TypeError):
                pass
    if isinstance(value, dict) and isinstance(value.get("text"), str):
        return value["text"]
    return str(value or "")
