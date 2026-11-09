import re
from typing import Iterable


class RegexError(ValueError):
    def __init__(self, message: str):
        super().__init__(f"Regex invalid: {message}")


def validate_regex(pattern: str) -> None:
    try:
        re.compile(pattern)
    except re.error as e:
        raise RegexError(f"Pattern '{pattern}': {e}") from e


_REPL_PATTERN = re.compile(
    r"\$\$(?P<escaped>)|\$(?:\{(?P<braced>[a-zA-Z0-9_]+)\}|<(?P<angled>[a-zA-Z0-9_]+)>|(?P<numbered>[0-9]+))"
)


def to_python_replacement(template: str) -> str:
    """
    Convert replacement template syntax:
    - `$$` -> literal `$`
    - `$1`, `$2` -> `\\g<1>`, `\\g<2>`
    - `${name}` or `$<name>` -> `\\g<name>`
    """
    if "$" not in template:
        return template

    def _replace_match(m: re.Match) -> str:
        if m.group("escaped") is not None:
            return "$"
        name = m.group("braced") or m.group("angled") or m.group("numbered")
        return f"\\g<{name}>"

    return _REPL_PATTERN.sub(_replace_match, template)


def regex_sub(pattern: str, template: str, text: str) -> str:
    repl = to_python_replacement(template)
    return re.sub(pattern, repl, text)


def matches_pattern(pattern: str, text: str, regex: bool = False) -> bool:
    if not regex:
        return pattern == text
    return bool(re.search(pattern, text))


def matches_any_pattern(patterns: Iterable[str], text: str, regex: bool = False) -> bool:
    if not regex:
        return text in patterns
    return any(re.search(p, text) for p in patterns)


def validate_condition_regex(condition: dict) -> None:
    for k, v in condition.items():
        if isinstance(v, str):
            validate_regex(v)
        elif isinstance(v, dict):
            validate_condition_regex(v)


def validate_clauses(clauses: list[dict] | None) -> None:
    if not clauses:
        return
    for clause in clauses:
        validate_condition_regex(clause)


def validate_patterns(*pattern_groups: Iterable[str] | None) -> None:
    for group in pattern_groups:
        if not group:
            continue
        for pattern in group:
            if isinstance(pattern, str):
                validate_regex(pattern)
