import copy
import logging

from config_sailor.patch.base import locator
from config_sailor.patch.base.schemas import Query, QueryMode, QueryScope
from config_sailor.utils import json_helper
from config_sailor.utils.json_helper import JsonObject, JsonValue

logger = logging.getLogger(__name__)


def apply_queries(
        queries: list[Query],
        target: JsonValue,
) -> JsonValue:
    result = target
    for q in queries:
        result = apply_query(q, result)
    return result


def apply_query(
        query: Query,
        root: JsonValue,
) -> JsonValue:
    values = extract_source_values(query, root)
    return plant_destination_values(query, values, root)


def extract_source_values(
        query: Query,
        root: JsonValue,
) -> list[JsonValue]:
    target = resolve_scope_target(root, query.source.scope)
    if target is None:
        logger.warning(f"Source scope '{query.source.scope}' not found in document")
        return []

    candidates = normalize_to_object_array(target)
    use_regex = query.regex or query.source.regex
    indices = locator.apply_locate(query.source, candidates, regex=use_regex)
    matched = [candidates[i] for i in indices]

    return collect_plucked_values(matched, query)


def resolve_scope_target(
        root: JsonValue,
        scope: list[str],
) -> JsonValue | None:
    has_target, target = json_helper.resolve_path(root, scope)
    return target if has_target else None


def normalize_to_object_array(target: JsonValue) -> list[JsonObject]:
    if isinstance(target, dict):
        return [target]
    if isinstance(target, list):
        if not target:
            return []
        if any(not isinstance(i, dict) for i in target):
            raise ValueError(f"Scope target array elements must be objects")
        return target
    raise ValueError(f"Scope target must be an object or array of objects, got {type(target).__name__}")


def collect_plucked_values(
        items: list[JsonObject],
        query: Query,
) -> list[JsonValue]:
    results: list[JsonValue] = []
    for item in items:
        has_field, val = json_helper.resolve_path(item, query.pluck)
        if not has_field:
            if query.nullable:
                results.append(None)
            continue
        if val is None:
            if query.nullable:
                results.append(None)
            continue
        if isinstance(val, list) and query.flatten:
            for sub_val in val:
                if sub_val is None and not query.nullable:
                    continue
                results.append(sub_val)
        else:
            results.append(val)
    return results


def plant_destination_values(
        query: Query,
        values: list[JsonValue],
        root: JsonValue,
) -> JsonValue:
    dest_target = resolve_scope_target(root, query.destination.scope)
    if dest_target is None:
        logger.warning(f"Destination scope '{query.destination.scope}' not found in document")
        return root

    dest_objects = locate_destination_objects(dest_target, query.destination, query.regex)
    for obj in dest_objects:
        plant_field_in_object(obj, query, values)

    return root


def locate_destination_objects(
        dest_target: JsonValue,
        scope: QueryScope,
        regex: bool = False,
) -> list[JsonObject]:
    if isinstance(dest_target, dict):
        return [dest_target]
    if isinstance(dest_target, list):
        if not dest_target:
            return []
        if any(not isinstance(i, dict) for i in dest_target):
            raise ValueError(f"Destination array elements must be objects")
        use_regex = regex or scope.regex
        indices = locator.apply_locate(scope, dest_target, regex=use_regex)
        return [dest_target[i] for i in indices]
    raise ValueError(f"Destination target must be an object or array of objects, got {type(dest_target).__name__}")


def plant_field_in_object(
        obj: JsonObject,
        query: Query,
        values: list[JsonValue],
) -> None:
    curr = obj
    for step in query.plant[:-1]:
        if step not in curr or not isinstance(curr[step], dict):
            curr[step] = {}
        curr = curr[step]

    field = query.plant[-1]
    field_exists = field in curr
    existing_value = curr.get(field)

    curr[field] = compute_planted_value(existing_value, values, query, field_exists)


def compute_planted_value(
        existing: JsonValue,
        values: list[JsonValue],
        query: Query,
        field_exists: bool,
) -> JsonValue:
    new_values = copy.deepcopy(values)
    if query.mode == QueryMode.REPLACE:
        return new_values

    existing_list = normalize_existing_value(existing, query.nullable, field_exists)
    if query.mode == QueryMode.APPEND:
        return existing_list + new_values
    if query.mode == QueryMode.PREPEND:
        return new_values + existing_list

    raise ValueError(f"Unsupported query mode: {query.mode}")


def normalize_existing_value(
        existing: JsonValue,
        nullable: bool,
        field_exists: bool,
) -> list[JsonValue]:
    if not field_exists:
        return []
    if existing is None:
        return [None] if nullable else []
    if isinstance(existing, list):
        return list(existing)
    return [existing]
