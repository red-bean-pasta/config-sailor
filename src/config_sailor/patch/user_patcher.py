from pydantic import Field, field_validator, model_validator, BaseModel

from config_sailor.utils.json_helper import JsonObject
from config_sailor.patch import conditional_node_parser
from config_sailor.utils import json_helper
from config_sailor.patch import conditional_node_maker
from config_sailor.patch.base.schemas import SpecError
from config_sailor.utils.regex_helper import matches_any_pattern, validate_patterns, RegexError


class UserMixin(BaseModel):
    user: list[str] | bool = Field(alias='$user')

    @field_validator('user', mode='before')
    @classmethod
    def _normalize_user(cls, value):
        if isinstance(value, bool):
            return value
        return json_helper.as_list(value)

    @model_validator(mode='after')
    def _validate_user_regex(self):
        if getattr(self, 'regex', False) and not isinstance(self.user, bool):
            try:
                validate_patterns(self.user)
            except RegexError as e:
                raise SpecError(str(e)) from e
        return self


UserPatchNode = conditional_node_maker.make(UserMixin)


def patch(
        client_user: str,
        spec: str | bytes,
        config: JsonObject
) -> JsonObject:
    node = conditional_node_parser.parse(
        UserPatchNode,
        spec,
        _check_user,
        client_user
    )
    return node.patch(config)


def _check_user(
        client_user: str | bool,
        model: UserMixin
) -> bool:
    if isinstance(model.user, bool):
        return model.user
    if getattr(model, 'regex', False) and isinstance(client_user, str):
        return matches_any_pattern(model.user, client_user, regex=True)
    return client_user in model.user