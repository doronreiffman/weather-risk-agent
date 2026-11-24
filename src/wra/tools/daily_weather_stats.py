"""daily_weather_stats: measured daily snowfall or precipitation at a hub's airport station."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from wra.scoring.confidence import daily_confidence
from wra.tools.common import check_hubs
from wra.tools.context import ToolContext
from wra.tools.envelope import Display, Provenance, ToolResult, failure

DESCRIPTION = (
    "Measured daily snowfall or precipitation statistics for one hub's airport weather station: days observed, "
    "days missing, days meeting the threshold, trace days and the percentage of observed days. Use for "
    "questions such as 'what share of days had snowfall'. A null start_year or end_year means the last full "
    "calendar year, worked out here. Covers 2016 to 2025 only."
)


class DailyStatsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hub_id: str
    metric: Literal["snowfall", "precipitation"]
    start_year: int | None
    end_year: int | None
    threshold: Literal["measurable", "trace_or_more"]


class OutsidePeriod(ValueError):
    pass


def daily_weather_stats(ctx: ToolContext, args: DailyStatsArgs) -> ToolResult:
    check_hubs(ctx, [args.hub_id])
    cfg = ctx.config
    last_full = ctx.today.year - 1
    start = args.start_year if args.start_year is not None else last_full
    end = args.end_year if args.end_year is not None else last_full
    if start > end:
        return failure("daily_weather_stats", "invalid_arguments", f"start_year {start} is after end_year {end}.")
    if start < cfg.first_year or end > cfg.last_year:
        return failure(
            "daily_weather_stats",
            "no_data_for_period",
            f"Station data covers {cfg.first_year} to {cfg.last_year}; {_period(start, end)} was asked for.",
        )

    first, last = date(start, 1, 1), date(end, 12, 31)
    total = (last - first).days + 1
    days = [d for d in ctx.data.days[args.hub_id] if first <= d.day <= last]
    snow = args.metric == "snowfall"
    cut = cfg.daily.snowfall_measurable_in if snow else cfg.daily.precipitation_measurable_in
    measurable = trace = recorded_missing = 0
    for d in days:
        flag, amount = (d.snow_flag, d.snow_in) if snow else (d.precip_flag, d.precip_in)
        if flag == "M":
            recorded_missing += 1
        elif flag == "T":
            trace += 1
        elif amount is not None and amount >= cut:
            measurable += 1
    missing = recorded_missing + (total - len(days))  # a day absent from the record counts as missing
    observed = total - missing
    meeting = measurable + (trace if args.threshold == "trace_or_more" else 0)
    pct = round(100 * meeting / observed, 1) if observed else None
    period = _period(start, end)

    data = {
        "hub_id": args.hub_id, "metric": args.metric, "threshold": args.threshold, "threshold_in": cut,
        "period": period, "start_year": start, "end_year": end, "days_in_period": total,
        "days_observed": observed, "days_missing": missing, "days_meeting": meeting, "days_trace": trace,
        "pct_of_observed": pct,
    }  # fmt: skip
    confidence = daily_confidence(missing, total, cfg.daily)
    return ToolResult(
        ok=True,
        tool="daily_weather_stats",
        data=data,
        display=_display(ctx, data, snow),
        provenance=Provenance(
            sources=["noaa_station_acis"], period=period, data_as_of=ctx.data.data_as_of,
            confidence=confidence.label, confidence_reason=confidence.reason,
        ),  # fmt: skip
    )


def _period(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"


def _display(ctx: ToolContext, d: dict, snow: bool) -> Display:
    what = "snowfall" if snow else "precipitation"
    amount = f"{d['threshold_in']:g} in or more"
    meeting = f"Days with {amount}" if d["threshold"] == "measurable" else f"Days with a trace or {amount}"
    kind = f"measurable {what}" if d["threshold"] == "measurable" else f"a trace or more of {what}"
    station = ctx.data.hubs[d["hub_id"]].station_name
    if snow:
        what_counts = (
            f"Measured at the {station} station. Measurable snowfall is {d['threshold_in']:g} inch or more in a "
            "day. Trace days are counted apart. Missing days are left out of the percentage."
        )
    else:
        what_counts = (
            f"Measured at the {station} station. A day with precipitation means {d['threshold_in']:g} inch or more, "
            "any recorded amount. Trace days are counted apart. Missing days are left out of the percentage. "
            "This describes the weather at the station, not disruption."
        )
    return Display(
        title=f"{ctx.label(d['hub_id'])}: days with {kind}, {d['period']}",
        columns=["Measure", "Value"],
        rows=[
            [meeting, d["days_meeting"]],
            ["Days with a trace only", d["days_trace"]],
            ["Days observed", d["days_observed"]],
            ["Days missing", d["days_missing"]],
            ["Share of observed days (%)", d["pct_of_observed"]],
        ],
        what_counts=what_counts,
    )
