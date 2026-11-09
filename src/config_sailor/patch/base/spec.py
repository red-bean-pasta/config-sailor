import logging
from typing import Any, Callable, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

import config_sailor.patch.base.filter as strain
from config_sailor.utils.json_helper import JsonValue, as_list
from config_sailor.patch.base import selector, modifier, inserter, replacer, querier
from config_sailor.patch.base.schemas import Select, Filter, Replace, Modify, Insert, Query


logger = logging.getLogger(__name__)


class PatchNode(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        extra='forbid'
    )

    filter: list[Filter] | None = Field(default=None, alias='$filter')
    select: list[Select] | None = Field(default=None, alias='$select')
    insert: list[Insert] | None = Field(default=None, alias='$insert')
    query: list[Query] | None = Field(default=None, alias='$query')
    modify: list[Modify] | None = Field(default=None, alias='$modify')
    replace: list[Replace] | None = Field(default=None, alias='$replace')

    children: dict[str, Self] = Field(default_factory=dict, alias='$children')

    @model_validator(mode='before')
    @classmethod
    def _split_children(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        children: dict[str, Any] = {}
        normalized: dict[str, Any] = {}
        for key, value in data.items():
            if key in ['$filter', '$select', '$insert', '$query', '$modify', '$replace']:
                normalized[key] = value
            else:
                children[key] = value
        if children:
            normalized['$children'] = children

        return normalized

    @field_validator('select', 'replace', 'filter', 'modify', 'insert', 'query', mode='before')
    @classmethod
    def _normalize_single_field(cls, value) -> list[JsonValue] | None:
        return as_list(value)

    ordered_directives: dict[str, Callable[[list[BaseModel], JsonValue], JsonValue]] = {
        'filter': strain.apply_filters,
        'select': selector.apply_selects,
        'insert': inserter.apply_inserts,
        'query': querier.apply_queries,
        'modify': modifier.apply_modifies,
        'replace': replacer.apply_replaces,
    }
    def patch(self, target: JsonValue) -> JsonValue:
        result = target
        for directive in ['filter', 'select', 'insert']:
            if values := getattr(self, directive):
                result = self.ordered_directives[directive](values, result)

        for key, child in self.children.items():
            if not isinstance(result, dict):
                logger.warning(f"Cannot patch child key '{key}' on non-dict target of type {type(result).__name__}")
                continue
            if key not in result:
                logger.warning(f"Skip patching on key '{key}': Not found")
                continue
            result[key] = child.patch(result[key])

        for directive in ['query', 'modify', 'replace']:
            if values := getattr(self, directive):
                result = self.ordered_directives[directive](values, result)

        return result