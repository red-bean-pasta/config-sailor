from config_sailor.utils.json_helper import JsonObject, JsonValue
from config_sailor.patch.base import locator, combiner
from config_sailor.utils.json_helper import ensure_object_array
from config_sailor.patch.base.schemas import Filter


def apply_filters(
        filters: list[Filter],
        target: JsonValue
) -> list[JsonObject]:
    target = ensure_object_array(target)

    accumulated: list[int] = []
    for f in filters:
        new = apply_filter(f, target)
        accumulated = combiner.apply_combine(f, accumulated, new)
    return [target[i] for i in accumulated]


def apply_filter(
        filter: Filter,
        targets: list[JsonObject]
) -> list[int]:
    return locator.apply_locate(filter, targets)