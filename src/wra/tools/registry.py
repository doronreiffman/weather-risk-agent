"""The six tools by name: each with its argument model, its function and the description sent to the model.

run_tool is the one entry point. It validates the arguments with Pydantic and
turns every refusal into an error result, so a bad call never raises.
"""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from wra.tools import compare_hubs, daily_weather_stats, explain_hub, get_methodology, list_hubs, rank_hubs
from wra.tools.common import UnknownHub
from wra.tools.context import ToolContext
from wra.tools.envelope import ToolResult, failure


@dataclass(frozen=True)
class Tool:
    name: str
    args: type[BaseModel]
    run: Callable[[ToolContext, BaseModel], ToolResult]
    description: str


TOOLS = {
    t.name: t
    for t in (
        Tool("list_hubs", list_hubs.ListHubsArgs, list_hubs.list_hubs, list_hubs.DESCRIPTION),
        Tool("rank_hubs", rank_hubs.RankHubsArgs, rank_hubs.rank_hubs, rank_hubs.DESCRIPTION),
        Tool("compare_hubs", compare_hubs.CompareHubsArgs, compare_hubs.compare_hubs, compare_hubs.DESCRIPTION),
        Tool("explain_hub", explain_hub.ExplainHubArgs, explain_hub.explain_hub, explain_hub.DESCRIPTION),
        Tool(
            "daily_weather_stats",
            daily_weather_stats.DailyStatsArgs,
            daily_weather_stats.daily_weather_stats,
            daily_weather_stats.DESCRIPTION,
        ),
        Tool(
            "get_methodology",
            get_methodology.MethodologyArgs,
            get_methodology.get_methodology,
            get_methodology.DESCRIPTION,
        ),
    )
}


def run_tool(ctx: ToolContext, name: str, raw_args: dict) -> ToolResult:
    tool = TOOLS.get(name)
    if tool is None:
        return failure(name, "unknown_tool", f"No tool named {name!r}. Tools: {', '.join(TOOLS)}.")
    try:
        args = tool.args.model_validate(raw_args)
    except ValidationError as error:
        problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in error.errors())
        return failure(name, "invalid_arguments", problems)
    try:
        return tool.run(ctx, args)
    except UnknownHub as error:
        return failure(name, "unknown_hub", str(error))
    except ValueError as error:  # an impossible weight change, for example
        return failure(name, "invalid_arguments", str(error))
