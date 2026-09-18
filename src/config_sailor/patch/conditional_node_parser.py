from typing import Callable, TypeVar

from config_sailor.patch.base.spec import PatchNode
from config_sailor.utils.json_helper import JsonValue
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


def parse(
        node_type: type[PatchNode],
        spec: str | bytes,
        qualifier: Callable[[JsonValue, T], bool],
        value: str,
) -> PatchNode:
    node = node_type.model_validate_json(spec)
    return _qualify_node(value, node, qualifier)


def _qualify_node(
        value: JsonValue,
        node: PatchNode,
        qualifier: Callable[[JsonValue, T], bool],
) -> PatchNode:
    normalized = PatchNode()

    for field in normalized.ordered_directives:
        models = getattr(node, field)
        applicable = [m for m in models if qualifier(value, m)] if models else models
        setattr(normalized, field, applicable)

    for key, child in node.children.items():
        normalized.children[key] = _qualify_node(value, child, qualifier)

    return normalized