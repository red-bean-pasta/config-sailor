import logging
from typing import Annotated

from packaging.specifiers import SpecifierSet
from packaging.version import Version
from pydantic import Field, BaseModel, PlainValidator, PlainSerializer

from config_sailor.utils.json_helper import JsonObject
from config_sailor.patch import conditional_node_maker, conditional_node_parser


logger = logging.getLogger(__name__)


PydanticSpecifierSet = Annotated[
    SpecifierSet,
    PlainValidator(lambda v: SpecifierSet(v)),
    PlainSerializer(lambda v: str(v), return_type=str)
]

class VersionMixin(BaseModel):
    version: PydanticSpecifierSet = Field(alias='$version')


VersionPatchNode = conditional_node_maker.make(VersionMixin)


def patch(
        client_version: str,
        spec: str | bytes,
        config: JsonObject
) -> JsonObject:
    node = conditional_node_parser.parse(
        VersionPatchNode,
        spec,
        _check_version,
        client_version
    )
    return node.patch(config)


def _check_version(
        client_version: str,
        model: VersionMixin
) -> bool:
    return Version(client_version) in model.version