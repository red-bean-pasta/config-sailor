from config_sailor.utils.json_helper import JsonObject, JsonValue, ensure_object_array
from config_sailor.patch.base import locator
from config_sailor.patch.base.schemas import Insert


def apply_inserts(
        inserts: list[Insert],
        target: JsonValue
) -> list[JsonObject]:
    target = ensure_object_array(target)

    result = target
    for i in inserts:
        result = apply_insert(i, result)
    return result


def apply_insert(
        insert: Insert,
        targets: list[JsonObject],
) -> list[JsonObject]:
    selection = locator.apply_locate(insert, targets)
    if insert.index is None:
        index = selection[-1] + 1
    else:
        assert len(selection) == 1
        index = selection[0]

    result = list(targets)
    result[index:index] = insert.value
    return result