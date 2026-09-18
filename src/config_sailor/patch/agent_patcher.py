from pydantic import Field, field_validator, BaseModel

from config_sailor.utils.json_helper import JsonObject
from config_sailor.patch import conditional_node_maker, conditional_node_parser
from config_sailor.utils import json_helper


class AgentMixin(BaseModel):
    agent: list[str] = Field(alias='$agent')

    @field_validator('agent', mode='before')
    @classmethod
    def _normalize_agent(cls, value):
        return json_helper.as_list(value)


AgentPatchNode = conditional_node_maker.make(AgentMixin)


def patch(
        client_agent: str,
        spec: str | bytes,
        config: JsonObject
) -> JsonObject:
    node = conditional_node_parser.parse(
        AgentPatchNode,
        spec,
        _check_agent,
        client_agent
    )
    return node.patch(config)


def _check_agent(
        client_agent: str,
        model: AgentMixin
) -> bool:
    return client_agent in model.agent