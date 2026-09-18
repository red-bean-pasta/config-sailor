from config_sailor.patch.base.schemas import Replace
from config_sailor.utils.json_helper import JsonObject, JsonValue, ensure_object_or_object_array


def apply_replaces(
        replaces: list[Replace],
        target: JsonValue,
) -> JsonObject | list[JsonObject]:
    target = ensure_object_or_object_array(target)

    result = target
    for r in replaces:
        result = apply_replace(r, result)
    return result


def apply_replace(
        replace: Replace,
        target: JsonObject | list[JsonObject],
) -> JsonObject | list[JsonObject]:
    if not isinstance(target, list):
        return _apply_replace_on_object(replace, target)

    result = list(target)
    for i, t in enumerate(target):
        result[i] = _apply_replace_on_object(replace, t)
    return result


def _apply_replace_on_object(
        replace: Replace,
        target: JsonObject
) -> JsonObject:
    assert isinstance(target, dict)

    result = target
    for k, v in target.items():
        result[k] = _apply_replace_on_value(replace, v)

    return result


def _apply_replace_on_value(
        replace: Replace,
        value: JsonValue
) -> JsonValue:
    if isinstance(value, str) and value in replace.from_:
        return replace.to

    if not replace.recursive:
        return value

    if isinstance(value, dict):
        return _apply_replace_on_object(replace, value)

    if isinstance(value, list):
        for i, item in enumerate(value):
            value[i] = _apply_replace_on_value(replace, item)
        return value

    return value