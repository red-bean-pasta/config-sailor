from enum import StrEnum

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator

from config_sailor.utils.json_helper import JsonValue, JsonObject, as_list


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


class Combine(BaseModel):
    model_config = _model_config

    mode: CombineMode | None = Field(default=CombineMode.UNION, alias='$mode')


class Locator(BaseModel):
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
    def _validate_slice(self):
        if not self.slice:
            return self
        for s in self.slice:
            l = len(s)
            if l == 2:
                s.append(None)
            elif l != 3:
                raise SpecError(f'$slice specified with {l} numbers: Only [start, end] and [start, end, step] forms are supported')
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


class Modify(BaseModel):
    model_config = _model_config

    if_: list[JsonObject] | None = Field(default=None, alias='$if')
    not_: list[JsonObject] | None = Field(default=None, alias='$not')
    to: list[Locator] | None = Field(default=None, alias='$to')

    remove: list[str] | None = Field(default=None, alias='$remove')
    prune: list[list[str]] | None = Field(default=None, alias='$prune')
    patch: JsonObject | None = Field(default=None, alias='$patch')
    assign: JsonObject | None = Field(default=None, alias='$assign')

    @field_validator('prune', mode='before')
    @classmethod
    def _normalize_prune(cls, value):
        if not value:
            return value
        if not isinstance(value, list):  # Let pydantic handle it
            return value
        if isinstance(value[0], list):  # [["a", "b"]]
            return value
        return [value]  # ["a", "b"] => [["a", "b"]]

    @field_validator('to', mode='before')
    @classmethod
    def _normalize_to(cls, value):
        if not value:
            return value
        if isinstance(value, int):
            return [{'$index': [value]}]
        if isinstance(value, list):
            return [{'$index': value}] if isinstance(value[0], int) else value
        if isinstance(value, dict):
            return [value] if any(k.startswith("$") for k in value) else [{'$where': value}]
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
        return self


class Replace(BaseModel):
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