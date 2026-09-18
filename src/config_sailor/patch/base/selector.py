from collections import defaultdict
from typing import Any

from config_sailor.utils.json_helper import JsonObject, get_indexed_items, JsonValue
from config_sailor.patch.base import combiner
from config_sailor.utils import json_helper
from config_sailor.utils.json_helper import ensure_object_array
from config_sailor.patch.base.schemas import Select


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
    selection = _apply_by_in(select.by, select.in_, targets)
    rename = _apply_rename(select.by, select.rename, targets, selection) if select.rename else {}
    normalized_rename = _normalize_rename(select.by, rename)
    override = _apply_override(select.by, select.override, targets, selection) if select.override else {}

    result = {}
    for i in selection:
        result[i] = [v for v in [normalized_rename.get(i), override.get(i)] if v]
    return result


def _apply_by_in(
        by: list[str],
        in_: list[str],
        targets: list[JsonObject],
) -> list[int]:
    result = []
    for i, t in enumerate(targets):
        for option in in_:
            if _compare_by_option(by, option, t):
                result.append(i)
                break
    return result


def _apply_rename(
        by: list[str],
        rename: dict[str, str],
        targets: list[JsonObject],
        selection: list[int] | None,
) -> dict[int, str]:
    return _convert_keyed_to_indexed(by, rename, targets, selection)


def _apply_override(
        by: list[str],
        override: dict[str, JsonObject],
        targets: list[JsonObject],
        selection: list[int] | None,
) -> dict[int, JsonObject]:
    return _convert_keyed_to_indexed(by, override, targets, selection)


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
) -> bool:
    value = target
    for key in by:
        if key not in value:
            return False
        value = value[key]
    return option == value


def _convert_keyed_to_indexed(
        by: list[str],
        keyed_dict: dict[str, Any],
        targets: list[JsonObject],
        selection: list[int] | None,
) -> dict[int, Any]:
    indexed_dict: dict[int, Any] = {}
    selected = _select_targets_by_indices(targets, selection)
    for i, s in selected.items():
        value = s
        for key in by:
            value = value[key]
        if value in keyed_dict:
            indexed_dict[i] = keyed_dict[value]
    return indexed_dict


def _select_targets_by_indices(
        targets: list[JsonObject],
        selection: list[int] | None,
) -> dict[int, JsonObject]:
    if selection is None:
        selection = range(len(targets))
    return get_indexed_items(selection, targets)