from pydantic import Field, field_validator, model_validator, BaseModel

from config_sailor.utils.json_helper import JsonObject
from config_sailor.patch import conditional_node_maker, conditional_node_parser
from config_sailor.utils import json_helper
from config_sailor.patch.base.schemas import SpecError
from config_sailor.utils.regex_helper import matches_any_pattern, validate_patterns, RegexError


class AgentMixin(BaseModel):
    agent: list[str] = Field(alias='$agent')

    @field_validator('agent', mode='before')
    @classmethod
    def _normalize_agent(cls, value):
        return json_helper.as_list(value)

    @model_validator(mode='after')
    def _validate_agent_regex(self):
        if getattr(self, 'regex', False):
            try:
                validate_patterns(self.agent)
            except RegexError as e:
                raise SpecError(str(e)) from e
        return self


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
    if getattr(model, 'regex', False) and isinstance(client_agent, str):
        return matches_any_pattern(model.agent, client_agent, regex=True)
    return client_agent in model.agent