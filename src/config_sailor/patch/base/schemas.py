from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator

from config_sailor.utils.json_helper import JsonValue, JsonObject, as_list
from config_sailor.utils.regex_helper import validate_regex, validate_clauses, validate_patterns, RegexError


class SpecError(ValueError):
    def __init__(self, message):
        super().__init__(f"Spec invalid: {message}")


class CombineMode(StrEnum):
    UNION = 'union'
    INTERSECT = 'intersect'
    DIFFERENCE = 'difference'
    APPEND = 'append'


_model_config = ConfigDict(
    validate_by_name=True,
    validate_by_alias=True,
    extra='forbid'
)


class Directive(BaseModel):
    model_config = _model_config

    regex: bool = Field(default=False, alias='$regex')


class Combine(Directive):
    model_config = _model_config

    mode: CombineMode | None = Field(default=CombineMode.UNION, alias='$mode')


class Locator(Directive):
    model_config = _model_config

    where: list[JsonObject] | None = Field(default=None, alias='$where')
    not_: list[JsonObject] | None = Field(default=None, alias='$not')
    slice: list[list[int | None]] | None = Field(default=None, alias='$slice')
    index: list[int] | None = Field(default=None, alias='$index')

    @field_validator('where', 'not_', 'index', mode='before')
    @classmethod
    def _normalize_single_field(cls, value) -> list[JsonValue] | None:
        return as_list(value)

    @field_validator('slice', mode='before')
    @classmethod
    def _normalize_slice(cls, value) -> list[list[int | None]] | None:
        if not value:
            return value
        if not isinstance(value, list):
            return value
        if isinstance(value[0], list):
            return value
        return [value]

    @model_validator(mode='after')
    def _validate_locator(self):
        if self.slice:
            for s in self.slice:
                l = len(s)
                if l == 2:
                    s.append(None)
                elif l != 3:
                    raise SpecError(f'$slice specified with {l} numbers: Only [start, end] and [start, end, step] forms are supported')
        if self.regex:
            try:
                validate_clauses(self.where)
                validate_clauses(self.not_)
            except RegexError as e:
                raise SpecError(str(e)) from e
        return self


class Select(Combine):
    model_config = _model_config

    by: list[str] = Field(alias='$by')
    in_: list[str] = Field(alias='$in')
    rename: dict[str, str] | None = Field(default=None, alias='$rename')
    override: dict[str, JsonObject] | None = Field(default=None, alias='$override')

    @field_validator('by', mode='before')
    @classmethod
    def _normalize_single_field(cls, value) -> list[JsonValue] | None:
        return as_list(value)

    @model_validator(mode='after')
    def _validate_select(self):
        if self.regex:
            try:
                validate_patterns(self.in_, self.rename, self.override)
            except RegexError as e:
                raise SpecError(str(e)) from e
        return self


class Filter(Combine, Locator):
    model_config = _model_config


class Insert(Locator):
    model_config = _model_config

    value: list[JsonObject] = Field(alias='$value')

    @field_validator('value', mode='before')
    @classmethod
    def _normalize_single_field(cls, value) -> list[JsonValue] | None:
        return as_list(value)

    @model_validator(mode='after')
    def _validate_insert(self):
        if self.slice is not None:
            raise SpecError('$slice is not allowed in $insert')
        if isinstance(self.index, list) and len(self.index) > 1:
            raise SpecError('$index cannot be multiple in $insert')
        return self


class Modify(Directive):
    model_config = _model_config

    if_: list[JsonObject] | None = Field(default=None, alias='$if')
    not_: list[JsonObject] | None = Field(default=None, alias='$not')
    to: list[Locator] | None = Field(default=None, alias='$to')

    remove: list[str] | None = Field(default=None, alias='$remove')
    drop: dict[str, list[JsonValue]] | None = Field(default=None, alias='$drop')
    prune: list[list[str]] | None = Field(default=None, alias='$prune')
    patch: JsonObject | None = Field(default=None, alias='$patch')
    assign: JsonObject | None = Field(default=None, alias='$assign')

    @field_validator('drop', mode='before')
    @classmethod
    def _normalize_drop(cls, value):
        if not value or not isinstance(value, dict):
            return value
        return {k: as_list(v) for k, v in value.items()}

    @field_validator('prune', mode='before')
    @classmethod
    def _normalize_prune(cls, value):
        if not value or not isinstance(value, list) or isinstance(value[0], list):
            return value
        return [value]

    @field_validator('to', mode='before')
    @classmethod
    def _normalize_to(cls, value):
        if not value:
            return value
        if isinstance(value, int):
            return [{'$index': [value]}]
        if isinstance(value, dict):
            return [value] if any(k.startswith("$") for k in value) else [{'$where': value}]
        if isinstance(value, list):
            if not value:
                return value
            if all(isinstance(x, int) for x in value):
                return [{'$index': value}]
            normalized = []
            for item in value:
                if isinstance(item, dict) and not any(k.startswith("$") for k in item):
                    normalized.append({'$where': item})
                else:
                    normalized.append(item)
            return normalized
        return value # Let pydantic handle

    @field_validator('if_', 'not_', 'remove', mode='before')
    @classmethod
    def _normalize_single_field(cls, value) -> list[JsonValue] | None:
        return as_list(value)

    @model_validator(mode='after')
    def _validate_modify(self):
        is_object = self.if_ is not None or self.not_ is not None
        is_array = self.to is not None
        if is_object and is_array:
            raise SpecError('$if and $not cannot be used together with $to in $modify')
        if self.regex:
            self._validate_modify_regex()
        return self

    def _validate_modify_regex(self) -> None:
        try:
            validate_clauses(self.if_)
            validate_clauses(self.not_)
            validate_patterns(self.remove)
            if self.drop:
                for patterns in self.drop.values():
                    validate_patterns(patterns)
            if self.prune:
                for path in self.prune:
                    validate_patterns(path)
        except RegexError as e:
            raise SpecError(str(e)) from e


class Replace(Directive):
    model_config = _model_config

    from_: list[str] = Field(alias='$from')
    to: JsonValue = Field(alias='$to')
    recursive: bool = Field(default=False, alias='$recursive')

    @field_validator('from_', mode='before')
    @classmethod
    def _normalize_single_field(cls, value) -> list[JsonValue] | None:
        if isinstance(value, str):
            return as_list(value)
        if not isinstance(value, list):
            raise SpecError(f'Invalid $from: Unexpected type: {type(value)}: Only string or string list is allowed')
        if not all(isinstance(i, str) for i in value):
            raise SpecError(f"Invalid $from: Only string element is allowed")
        return value

    @model_validator(mode='after')
    def _validate_replace(self):
        if self.regex:
            try:
                validate_patterns(self.from_)
            except RegexError as e:
                raise SpecError(str(e)) from e
        return self


class QueryMode(StrEnum):
    REPLACE = 'replace'
    APPEND = 'append'
    PREPEND = 'prepend'


def _normalize_string_list(value: Any, name: str) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and value and all(isinstance(k, str) for k in value):
        return value
    raise SpecError(f"Invalid {name}: Expecting non-empty string or list of strings, got {value}")


class QueryScope(Locator):
    model_config = _model_config

    scope: list[str] = Field(alias='$scope')

    @field_validator('scope', mode='before')
    @classmethod
    def _normalize_scope(cls, value: Any) -> list[str]:
        return _normalize_string_list(value, "$scope")


class Query(Directive):
    model_config = _model_config

    source: QueryScope = Field(alias='$source')
    pluck: list[str] = Field(alias='$pluck')
    destination: QueryScope = Field(alias='$destination')
    plant: list[str] = Field(alias='$plant')
    mode: QueryMode = Field(default=QueryMode.REPLACE, alias='$mode')
    flatten: bool = Field(default=False, alias='$flatten')
    nullable: bool = Field(default=True, alias='$nullable')

    @field_validator('pluck', 'plant', mode='before')
    @classmethod
    def _normalize_path(cls, value: Any) -> list[str]:
        return _normalize_string_list(value, "field path")

    @model_validator(mode='after')
    def _validate_query(self):
        if self.regex:
            try:
                validate_clauses(self.source.where)
                validate_clauses(self.source.not_)
                validate_clauses(self.destination.where)
                validate_clauses(self.destination.not_)
            except RegexError as e:
                raise SpecError(str(e)) from e
        return self
