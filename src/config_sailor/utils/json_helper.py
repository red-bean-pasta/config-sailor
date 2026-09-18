import copy
import json
from typing import Iterable, TypeAlias, TYPE_CHECKING
from typing_extensions import TypeAliasType


JsonScalar: TypeAlias = str | int | float | bool | None
if TYPE_CHECKING:
    JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
    JsonObject: TypeAlias = dict[str, JsonValue]
else: # Pydantic can't reliably build model with TypeAlias
    JsonValue = TypeAliasType(
        "JsonValue",
        "JsonScalar | list[JsonValue] | dict[str, JsonValue]",
    )
    JsonObject = TypeAliasType(
        "JsonObject",
        "dict[str, JsonValue]",
    )


def dump_readable(v: dict) -> str:
    return json.dumps(v, indent=4, ensure_ascii=False)


def ensure_object_or_object_array(
        target: JsonValue,
) -> JsonObject | list[JsonObject]:
    if isinstance(target, dict):
        return target
    if isinstance(target, list) and all(isinstance(i, dict) for i in target):
        return target
    raise ValueError(f"Config invalid: Expecting object or array, received {type(target)}")


def ensure_object_array(
        target: JsonValue,
        object_as_list: bool = True
) -> list[JsonObject]:
    """
    :param target:
    :param object_as_list: Treat object as list with single item
    :return: validated target
    """
    if object_as_list and isinstance(target, dict):
        target = [target]
    if not isinstance(target, list) or any(not isinstance(i, dict) for i in target):
        raise ValueError(f"Config invalid: Expecting array, received {type(target)}")
    return target


def get_indexed_items(
        indices: Iterable[int],
        target: list[JsonObject],
) -> dict[int, JsonObject]:
    assert indices is not None
    return {i:target[i] for i in indices}


def override_object(
        override: JsonObject,
        target: JsonObject,
) -> JsonObject:
    clone = copy.copy(target)
    for k, v in override.items():
        if k not in target:
            clone[k] = v
            continue
        if isinstance(clone[k], dict) and isinstance(v, dict):
            override_object(clone[k], v)
            continue
        clone[k] = v
    return clone


def shallow_recursive_compare(
        condition: JsonObject,
        target: JsonObject,
) -> bool:
    for k, v in condition.items():
        if k not in target:
            return False
        if type(target[k]) != type(v):
            return False
        if not isinstance(v, dict):
            if v != target[k]:
                return False
            continue
        if not shallow_recursive_compare(v, target[k]):
            return False
    return True


def as_list(x: JsonValue) -> list[JsonValue] | None:
    """
    None is kept as is
    """
    if x is None:
        return None
    if isinstance(x, list):
        return list(x) # Shallow copy
    return [x]