from collections import defaultdict
from typing import Any, Callable

from config_sailor.utils.json_helper import JsonObject, get_indexed_items, JsonValue
from config_sailor.patch.base import combiner
from config_sailor.utils import json_helper
from config_sailor.utils.json_helper import ensure_object_array
from config_sailor.patch.base.schemas import Select
from config_sailor.utils.regex_helper import matches_pattern, regex_sub


def apply_selects(
        selects: list[Select],
        target: JsonValue,
) -> list[JsonObject]:
    target = ensure_object_array(target)

    accumulated: list[int] = []
    overrides: defaultdict[int, list[JsonObject]] = defaultdict(list)
    for s in selects:
        new = apply_select(s, target)
        for i, o in new.items():
            overrides[i].extend(o)
        accumulated = combiner.apply_combine(s, accumulated, new.keys())

    result: list[JsonObject] = []
    for i in accumulated:
        overridden = _merge_with_overrides(target[i], overrides[i])
        result.append(overridden)
    return result


def apply_select(
        select: Select,
        targets: list[JsonObject],
) -> dict[int, list[JsonObject]]:
    selection = _apply_by_in(select.by, select.in_, targets, select.regex)
    selected = _select_targets_by_indices(targets, selection)
    rename = _apply_rename(select, selected) if select.rename else {}
    normalized_rename = _normalize_rename(select.by, rename)
    override = _apply_override(select, selected) if select.override else {}

    result = {}
    for i in selection:
        result[i] = [v for v in [normalized_rename.get(i), override.get(i)] if v]
    return result


def _apply_by_in(
        by: list[str],
        in_: list[str],
        targets: list[JsonObject],
        regex: bool = False,
) -> list[int]:
    result = []
    for i, t in enumerate(targets):
        for option in in_:
            if _compare_by_option(by, option, t, regex):
                result.append(i)
                break
    return result


def _apply_rename(
        select: Select,
        selected: dict[int, JsonObject],
) -> dict[int, str]:
    return _apply_keyed_mapping(
        select.by, select.rename, selected, regex=select.regex,
        transform=lambda p, repl, v: regex_sub(p, repl, v)
    )


def _apply_override(
        select: Select,
        selected: dict[int, JsonObject],
) -> dict[int, JsonObject]:
    return _apply_keyed_mapping(select.by, select.override, selected, regex=select.regex)


def _apply_keyed_mapping(
        by: list[str],
        mapping: dict[str, Any],
        selected: dict[int, JsonObject],
        regex: bool = False,
        transform: Callable[[str, Any, str], Any] | None = None,
) -> dict[int, Any]:
    if not regex:
        return _convert_keyed_to_indexed(by, mapping, selected)

    indexed_dict: dict[int, Any] = {}
    for i, s in selected.items():
        has_val, value = json_helper.resolve_path(s, by)
        if not has_val or not isinstance(value, str):
            continue
        for pattern, item in mapping.items():
            if matches_pattern(pattern, value, regex=True):
                indexed_dict[i] = transform(pattern, item, value) if transform else item
                break
    return indexed_dict


def _merge_with_overrides(
        target: JsonObject,
        overrides: list[JsonObject],
) -> JsonObject:
    result = target
    for o in overrides:
        result = json_helper.override_object(o, result)
    return result


def _normalize_rename(
        by: list[str],
        indexed_rename: dict[int, str],
) -> dict[int, JsonObject]:
    result = {}
    for i, r in indexed_rename.items():
        o = r
        for key in reversed(by):
            o = {key: o}
        result[i] = o
    return result


def _compare_by_option(
        by: list[str],
        option: JsonValue,
        target: JsonObject,
        regex: bool = False,
) -> bool:
    has_val, value = json_helper.resolve_path(target, by)
    if not has_val:
        return False
    if regex and isinstance(option, str) and isinstance(value, str):
        return matches_pattern(option, value, regex=True)
    return option == value


def _convert_keyed_to_indexed(
        by: list[str],
        keyed_dict: dict[str, Any],
        selected: dict[int, JsonObject],
) -> dict[int, Any]:
    indexed_dict: dict[int, Any] = {}
    for i, s in selected.items():
        has_val, value = json_helper.resolve_path(s, by)
        if has_val and value in keyed_dict:
            indexed_dict[i] = keyed_dict[value]
    return indexed_dict


def _select_targets_by_indices(
        targets: list[JsonObject],
        selection: list[int] | None,
) -> dict[int, JsonObject]:
    if selection is None:
        selection = range(len(targets))
    return get_indexed_items(selection, targets)