import logging
from typing import Any, Callable, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

import config_sailor.patch.base.filter as strain
from config_sailor.utils.json_helper import JsonValue, as_list
from config_sailor.patch.base import selector, modifier, inserter, replacer
from config_sailor.patch.base.schemas import Select, Filter, Replace, Modify, Insert


logger = logging.getLogger(__name__)


class PatchNode(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        extra='forbid'
    )

    filter: list[Filter] | None = Field(default=None, alias='$filter')
    select: list[Select] | None = Field(default=None, alias='$select')
    replace: list[Replace] | None = Field(default=None, alias='$replace')
    modify: list[Modify] | None = Field(default=None, alias='$modify')
    insert: list[Insert] | None = Field(default=None, alias='$insert')

    children: dict[str, Self] = Field(default_factory=dict, alias='$children')

    @model_validator(mode='before')
    @classmethod
    def _split_children(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        children: dict[str, Any] = {}
        normalized: dict[str, Any] = {}
        for key, value in data.items():
            if key in ['$filter', '$select', '$replace', '$modify', '$insert']:
                normalized[key] = value
            else:
                children[key] = value
        if children:
            normalized['$children'] = children

        return normalized

    @field_validator('select', 'replace', 'filter', 'modify', 'insert', mode='before')
    @classmethod
    def _normalize_single_field(cls, value) -> list[JsonValue] | None:
        return as_list(value)

    ordered_directives: dict[str, Callable[[list[BaseModel], JsonValue], JsonValue]] = {
        'filter': strain.apply_filters,
        'select': selector.apply_selects,
        'insert': inserter.apply_inserts,
        'modify': modifier.apply_modifies,
        'replace': replacer.apply_replaces,
    }
    def patch(self, target: JsonValue) -> JsonValue:
        result = target
        for directive, func in self.ordered_directives.items():
            if values := getattr(self, directive):
                result = func(values, result)
        for key, child in self.children.items():
            assert(isinstance(result, list) and isinstance(key, int) or isinstance(result, dict) and isinstance(key, str))
            if key not in result:
                logger.warning(f"Skip patching on key '{key}': Not found")
                continue
            result[key] = child.patch(result[key])
        return result