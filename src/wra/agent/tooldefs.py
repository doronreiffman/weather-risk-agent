"""The six tools and the final-answer schema as sent to Claude, generated from the Pydantic models.

Strict mode guarantees that arguments match the schema, but it supports only part
of JSON Schema: no numeric bounds, no length limits, no complex array limits, and
every object needs `additionalProperties: false` with all its properties
required. So the schema sent to the API is the Pydantic one with those
constraints removed; Pydantic still enforces them in code (registry.run_tool).
Hub ids become an enumeration of the twelve, so the model cannot ask about a
city with no hub (plan section 8.1).
"""

from typing import Any

from pydantic import BaseModel

from wra.agent.schemas import FinalAnswer
from wra.tools.registry import TOOLS

_DROP = {"title", "default", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
         "minLength", "maxLength", "minItems", "maxItems", "pattern", "uniqueItems"}  # fmt: skip
_HUB_FIELDS = {"hub_id", "hub_ids", "hubs_ranked", "hubs"}

RESULT_NOTE = (
    " Each result carries a result_id (R1, R2, ...): cite it in the final answer's evidence to show that "
    "result's table."
)


def strict_schema(model: type[BaseModel], hub_ids: list[str]) -> dict[str, Any]:
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})
    return _clean(raw, defs, hub_ids, field=None)


def tool_definitions(hub_ids: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description + RESULT_NOTE,
            "strict": True,
            "input_schema": strict_schema(tool.args, hub_ids),
        }
        for tool in TOOLS.values()
    ]


def final_answer_schema(hub_ids: list[str]) -> dict[str, Any]:
    return strict_schema(FinalAnswer, hub_ids)


def _clean(node: Any, defs: dict, hub_ids: list[str], field: str | None) -> Any:
    if isinstance(node, list):
        return [_clean(item, defs, hub_ids, field) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        return _clean(defs[node["$ref"].rsplit("/", 1)[-1]], defs, hub_ids, field)
    out = {}
    for key, value in node.items():
        if key in _DROP:
            continue
        if key == "properties":
            out[key] = {name: _clean(prop, defs, hub_ids, name) for name, prop in value.items()}
        else:
            out[key] = _clean(value, defs, hub_ids, field)
    if out.get("type") == "object":
        out["additionalProperties"] = False
        out["required"] = list(out.get("properties", {}))
        out.setdefault("properties", {})
    if field in _HUB_FIELDS and out.get("type") == "string":
        out["enum"] = list(hub_ids)
    return out
