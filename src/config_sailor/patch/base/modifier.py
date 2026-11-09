import copy
from typing import Callable, Any

from config_sailor.patch.base import locator
from config_sailor.patch.base.schemas import Modify, Locator
from config_sailor.utils.json_helper import JsonObject, shallow_recursive_compare, override_object, JsonValue, ensure_object_or_object_array
from config_sailor.utils.regex_helper import matches_pattern, matches_any_pattern


def apply_modifies(
        modifies: list[Modify],
        target: JsonValue,
) -> JsonObject | list[JsonObject]:
    target = ensure_object_or_object_array(target)

    result = target
    for m in modifies:
        result = apply_modify(m, result)
    return result


def apply_modify(
        modify: Modify,
        target: JsonObject | list[JsonObject],
) -> JsonObject | list[JsonObject]:
    is_object = _validate(modify, target)
    return _modify_object(modify, target) if is_object else _modify_array(modify, target)


def _validate(
        modify: Modify,
        target: JsonObject | list[JsonObject]
) -> bool:
    """
    :return: if object
    """
    m_object = modify.if_ is not None or modify.not_ is not None
    m_array = modify.to is not None
    t_object = isinstance(target, dict)
    t_array = (isinstance(target, list) and all(isinstance(i, dict) for i in target)
               or isinstance(target, dict))

    if m_object and m_array:
        raise AssertionError("Modifying with both `if`/`not` and `to` defined")
    if m_object and not t_object:
        raise ValueError(f"Trying to apply `if` and `not` on field of invalid type: {type(target)}")
    if m_array and not t_array:
        raise ValueError(f"Trying to apply `to` on field of invalid type: {type(target)}")

    if m_array:
        return False
    if m_object or t_object:
        return True
    return False


def _modify_object(
        modify: Modify,
        target: JsonObject
) -> JsonObject:
    passed_if = modify.if_ is None or _apply_if(modify.if_, target, modify.regex)
    passed_not = modify.not_ is None or _apply_not(modify.not_, target, modify.regex)
    if not passed_if or not passed_not:
        return target
    return _apply_operations(modify, target)


def _modify_array(
        modify: Modify,
        targets: list[JsonObject] | JsonObject
) -> list[JsonObject]:
    result = list(targets) if isinstance(targets, list) else [targets]
    selection = _apply_to(modify.to, targets, modify.regex) if modify.to else range(len(result))
    for i in selection:
        result[i] = _apply_operations(modify, result[i])
    return result


def _apply_operations(
        modify: Modify,
        target: JsonObject
) -> JsonObject:
    result = target
    for attr, func in _ordered_operations.items():
        value = getattr(modify, attr)
        if value is not None:
            if attr in ("remove", "prune", "drop"):
                result = func(value, result, modify.regex)
            else:
                result = func(value, result)
    return result


def _apply_if(
        if_: list[JsonObject],
        target: JsonObject,
        regex: bool = False,
) -> bool:
    for clause in if_:
        if shallow_recursive_compare(clause, target, regex=regex):
            return True
    return False


def _apply_not(
        not_: list[JsonObject],
        target: JsonObject,
        regex: bool = False,
) -> bool:
    return not _apply_if(not_, target, regex=regex)


def _apply_to(
        to_: list[Locator],
        targets: list[JsonObject],
        regex: bool = False,
) -> list[int]:
    return locator.apply_locators(to_, targets, regex=regex)


def _apply_remove(
        remove: list[str],
        target: JsonObject,
        regex: bool = False,
) -> JsonObject:
    result = dict(target)
    if not regex:
        for k in remove:
            result.pop(k, None)
        return result

    for k in [k for k in result if matches_any_pattern(remove, k, regex=True)]:
        del result[k]
    return result


def _should_drop_item(
        item: Any,
        patterns: list[JsonValue],
        str_patterns: list[str],
        regex: bool = False,
) -> bool:
    if regex and isinstance(item, str):
        if matches_any_pattern(str_patterns, item, regex=True):
            return True
    return item in patterns


def _apply_drop(
        drop: dict[str, list[JsonValue]],
        target: JsonObject,
        regex: bool = False,
) -> JsonObject:
    result = dict(target)
    for field_name, patterns in drop.items():
        if field_name not in result:
            continue
        val = result[field_name]
        if isinstance(val, list):
            str_patterns = [p for p in patterns if isinstance(p, str)] if regex else []
            result[field_name] = [
                item for item in val
                if not _should_drop_item(item, patterns, str_patterns, regex=regex)
            ]
    return result


def _apply_prune(
        prune: list[list[str]],
        target: JsonObject,
        regex: bool = False,
) -> JsonObject:
    result = copy.deepcopy(target)
    for p in prune:
        _prune_path(result, p, regex=regex)
    return result


def _prune_path(
        scope: JsonObject,
        path: list[str],
        regex: bool = False,
) -> None:
    if not path or not isinstance(scope, dict):
        return
    head, *tail = path
    if not tail:
        for k in [k for k in scope if matches_pattern(head, k, regex=regex)]:
            del scope[k]
        return
    for s in [k for k in scope if isinstance(scope[k], dict) and matches_pattern(head, k, regex=regex)]:
        _prune_path(scope[s], tail, regex=regex)


def _apply_patch(
        patch: JsonObject,
        target: JsonObject
) -> JsonObject:
    return override_object(patch, target)


def _apply_assign(
        assign: JsonObject,
        target: JsonObject
) -> JsonObject:
    result = dict(target)
    for k, v in assign.items():
        result[k] = v
    return result


_ordered_operations: dict[str, Callable[..., JsonObject]] = {
    "remove": _apply_remove,
    "drop": _apply_drop,
    "prune": _apply_prune,
    "patch": _apply_patch,
    "assign": _apply_assign,
}