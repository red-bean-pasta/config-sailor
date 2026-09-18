from typing import Callable, Any

from config_sailor.utils.json_helper import JsonObject, get_indexed_items, JsonValue
from config_sailor.utils.json_helper import ensure_object_array
from config_sailor.patch.base.schemas import Locator


def apply_locators(
        locators: list[Locator],
        target: JsonValue,
) -> list[int]:
    target = ensure_object_array(target)

    seen = set()
    result = []
    for l in locators:
        new = apply_locate(l, target)
        for i in new:
            if i not in seen:
                seen.add(i)
                result.append(i)
    return result


def apply_locate(
        locator: Locator,
        targets: list[JsonObject],
) -> list[int]:
    result = list(range(len(targets)))
    for attr, func in _ordered_locators.items():
        if (value := getattr(locator, attr)) is not None:
            result = func(value, targets, result)
    return result


def _apply_where(
        clauses: list[JsonObject],
        targets: list[JsonObject],
        selection: list[int],
) -> list[int]:
    selected = get_indexed_items(selection, targets)

    seen: set[int] = set()
    qualified: list[int] = []
    for w in clauses:
        for i, v in selected.items():
            if _recursive_compare(w, v) and i not in seen:
                seen.add(i)
                qualified.append(i)

    result = list(qualified)
    result.sort()
    return result


def _apply_not(
        clauses: list[JsonObject],
        targets: list[JsonObject],
        selection: list[int],
) -> list[int]:
    matched = _apply_where(clauses, targets, selection)
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


def _recursive_compare(
        left: JsonObject,
        right: JsonObject,
) -> bool:
    for k, v in left.items():
        if k not in right:
            return False
        c = right[k]
        if type(v) != type(c):
            return False
        if not isinstance(v, dict):
            if v != c:
                return False
            continue
        if not _recursive_compare(v, c):
            return False
    return True


_ordered_locators: dict[str, Callable[[Any, list[JsonObject], list[int] | None], list[int]]] = {
    'where': _apply_where,
    'not_': _apply_not,
    'slice': _apply_slice,
    'index': _apply_index,
}