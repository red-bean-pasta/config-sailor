from pydantic import Field, field_validator, BaseModel

from config_sailor.utils.json_helper import JsonObject
from config_sailor.patch import conditional_node_parser
from config_sailor.utils import json_helper
from config_sailor.patch import conditional_node_maker


class UserMixin(BaseModel):
    user: list[str] | bool = Field(alias='$user')

    @field_validator('user', mode='before')
    @classmethod
    def _normalize_user(cls, value):
        if isinstance(value, bool):
            return value
        return json_helper.as_list(value)


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
    return client_user in model.user if not isinstance(model.user, bool) else model.user