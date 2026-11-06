from typing import Callable, Any

from config_sailor.utils.json_helper import JsonObject, get_indexed_items, JsonValue
from config_sailor.utils.json_helper import ensure_object_array, shallow_recursive_compare
from config_sailor.patch.base.schemas import Locator


def apply_locators(
        locators: list[Locator],
        target: JsonValue,
        regex: bool = False,
) -> list[int]:
    target = ensure_object_array(target)

    seen = set()
    result = []
    for l in locators:
        use_regex = l.regex or regex
        new = apply_locate(l, target, regex=use_regex)
        for i in new:
            if i not in seen:
                seen.add(i)
                result.append(i)
    return result


def apply_locate(
        locator: Locator,
        targets: list[JsonObject],
        regex: bool = False,
) -> list[int]:
    use_regex = locator.regex or regex
    result = list(range(len(targets)))
    for attr, func in _ordered_locators.items():
        if (value := getattr(locator, attr)) is not None:
            if attr in ('where', 'not_'):
                result = func(value, targets, result, regex=use_regex)
            else:
                result = func(value, targets, result)
    return result


def _apply_where(
        clauses: list[JsonObject],
        targets: list[JsonObject],
        selection: list[int],
        regex: bool = False,
) -> list[int]:
    selected = get_indexed_items(selection, targets)

    seen: set[int] = set()
    qualified: list[int] = []
    for w in clauses:
        for i, v in selected.items():
            if shallow_recursive_compare(w, v, regex=regex) and i not in seen:
                seen.add(i)
                qualified.append(i)

    result = list(qualified)
    result.sort()
    return result


def _apply_not(
        clauses: list[JsonObject],
        targets: list[JsonObject],
        selection: list[int],
        regex: bool = False,
) -> list[int]:
    matched = _apply_where(clauses, targets, selection, regex=regex)
    result = list(selection)
    for i in matched:
        result.remove(i)
    return result


def _apply_slice(
        clause: list[list[int | None]],
        targets: list[JsonObject],
        selection: list[int],
) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for c in clause:
        sliced = selection[c[0]:c[1]:c[2]]
        for i in sliced:
            if i not in seen:
                seen.add(i)
                result.append(i)
    return result


def _apply_index(
        clause: list[int],
        targets: list[JsonObject],
        selection: list[int],
) -> list[int]:
    return [selection[i] for i in clause]


_ordered_locators: dict[str, Callable[..., list[int]]] = {
    'where': _apply_where,
    'not_': _apply_not,
    'slice': _apply_slice,
    'index': _apply_index,
}