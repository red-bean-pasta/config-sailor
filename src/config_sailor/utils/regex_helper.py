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


def to_python_replacement(template: str) -> str:
    """
    Convert replacement template syntax:
    - `$$` -> literal `$`
    - `$1`, `$2` -> `\\g<1>`, `\\g<2>`
    - `${name}` or `$<name>` -> `\\g<name>`
    """
    if "$" not in template:
        return template
    token = "\x00ESCAPED_DOLLAR\x00"
    s = template.replace("$$", token)
    s = re.sub(r"\$\{([a-zA-Z0-9_]+)\}", r"\\g<\1>", s)
    s = re.sub(r"\$<([a-zA-Z0-9_]+)>", r"\\g<\1>", s)
    s = re.sub(r"\$([0-9]+)", r"\\g<\1>", s)
    s = s.replace(token, "$")
    return s


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
