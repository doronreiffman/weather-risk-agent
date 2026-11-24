"""The one shape every tool returns (docs/PLAN.md, section 8.2).

`data` holds the figures the model may quote. `display` is the table the page
shows, built here by code, so the model never types a table. `provenance`
holds the sources, period, data date and the confidence worked out in code.
`display.notes` carries fixed caveats written by code, such as the winter note.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

SOURCE_NAMES = {
    "iem_warning_archive": "National Weather Service warnings, from the Iowa Environmental Mesonet archive",
    "fema_nri": "FEMA National Risk Index",
    "noaa_station_acis": "NOAA airport station observations, through the ACIS service",
}

# The Weather Service's names for the warning codes the score counts or shows.
WARNING_NAMES = {
    "WS": "Winter Storm",
    "BZ": "Blizzard",
    "IS": "Ice Storm",
    "LE": "Lake Effect Snow",
    "FF": "Flash Flood",
    "CF": "Coastal Flood",
    "TO": "Tornado",
    "SV": "Severe Thunderstorm",
    "HU": "Hurricane",
    "TR": "Tropical Storm",
    "SS": "Storm Surge",
}

# FEMA's own labels for the cross-check fields, as its map service names them.
FEMA_FIELD_NAMES = {
    "WNTW_AFREQ": "Winter Weather",
    "ISTM_AFREQ": "Ice Storm",
    "IFLD_AFREQ": "Inland Flooding",
    "CFLD_AFREQ": "Coastal Flooding",
    "TRND_AFREQ": "Tornado",
    "HAIL_AFREQ": "Hail",
    "SWND_AFREQ": "Strong Wind",
    "HRCN_AFREQ": "Hurricane",
}

Cell = str | int | float | None


class Display(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    columns: list[str]
    rows: list[list[Cell]]
    what_counts: str
    notes: list[str] = []


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: list[str]
    period: str
    data_as_of: str
    confidence: Literal["high", "medium", "low"]
    confidence_reason: str
    is_what_if: bool = False


class ToolError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Literal["invalid_arguments", "unknown_hub", "no_data_for_period", "unknown_tool"]
    message: str


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    tool: str
    data: dict[str, Any] | None = None
    display: Display | None = None
    provenance: Provenance | None = None
    error: ToolError | None = None


def failure(tool: str, code: str, message: str) -> ToolResult:
    return ToolResult(ok=False, tool=tool, error=ToolError(code=code, message=message))
