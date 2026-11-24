"""list_hubs: the hubs the agent knows, with where each one is."""

from pydantic import BaseModel, ConfigDict

from wra.scoring.confidence import Confidence
from wra.tools.common import Region
from wra.tools.context import ToolContext
from wra.tools.envelope import Display, Provenance, ToolResult

DESCRIPTION = (
    "List the hubs, for all regions or one: id, city, state, region, airport weather station and county. "
    "Use it to check whether a hub exists before answering about a city."
)


class ListHubsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    region: Region


def list_hubs(ctx: ToolContext, args: ListHubsArgs) -> ToolResult:
    hubs = [ctx.data.hubs[h] for h in ctx.hub_ids(args.region)]
    rows = [
        {"hub_id": h.hub_id, "city": h.city, "state": h.state, "region": h.region,
         "station": h.station_name, "county": f"{h.county_name} County"}
        for h in hubs
    ]  # fmt: skip
    disagree = [h.hub_id for h in hubs if h.county_check != "agree"]
    confidence = (
        Confidence("high", f"FEMA's county map and the warning archive name the same county for all {len(hubs)} hubs.")
        if not disagree
        else Confidence("medium", f"The two county maps disagree for {', '.join(disagree)}.")
    )
    where = "all regions" if args.region == "all" else f"the {args.region.capitalize()}"
    return ToolResult(
        ok=True,
        tool="list_hubs",
        data={"region": args.region, "hubs": rows},
        display=Display(
            title=f"Hubs in {where}",
            columns=["Hub", "City", "State", "Region", "Weather station", "County"],
            rows=[[r["hub_id"], r["city"], r["state"], r["region"].capitalize(), r["station"], r["county"]]
                  for r in rows],  # fmt: skip
            what_counts="Each hub sits at its city's main airport weather station (Dallas: Love Field). Its county "
            "is the one containing the station's coordinates. Regions follow the US Census Bureau's regions.",
        ),
        provenance=Provenance(
            sources=["noaa_station_acis", "fema_nri", "iem_warning_archive"], period=ctx.period,
            data_as_of=ctx.data.data_as_of, confidence=confidence.label, confidence_reason=confidence.reason,
        ),  # fmt: skip
    )
