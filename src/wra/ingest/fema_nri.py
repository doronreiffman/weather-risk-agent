"""FEMA National Risk Index: frequency figures for the county that contains a point.

Only frequencies are read. FEMA's headline scores and ratings are left out on
purpose (docs/PLAN.md, section 4.3). The hurricane frequency feeds the score;
the others are kept as an independent cross-check and are not scored.

What the hurricane frequency is, from FEMA's technical documentation (December
2025, sections 13 and 13.5): storms per year whose modelled wind area reaches
the 49 km grid cell around a place, counted over 1851 to 2024, tropical storms
included. The county figure is an area-weighted average over the county. A
place FEMA considers reachable but with no recorded storm gets a default of
0.01 a year. It is not a minimum: a place with one storm on record gets about
0.006, so a county's average can be lower than 0.01.

The service answers a bad query with HTTP 200 and an error in the body, so the
body is checked before anything is read from it.
"""

from dataclasses import dataclass

from wra.ingest.errors import SourceError
from wra.ingest.points import checked_point

QUERY_URL = (
    "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/"
    "National_Risk_Index_Counties/FeatureServer/0/query"
)

# Events per year, by FEMA's hazard code. Names as in the layer's field list.
FREQUENCY_FIELDS = (
    "HRCN_AFREQ",  # hurricane, tropical storms included
    "WNTW_AFREQ",  # winter weather
    "ISTM_AFREQ",  # ice storm
    "IFLD_AFREQ",  # inland flooding
    "CFLD_AFREQ",  # coastal flooding
    "TRND_AFREQ",  # tornado
    "HAIL_AFREQ",  # hail
    "SWND_AFREQ",  # strong wind
)
OUT_FIELDS = ("STCOFIPS", "COUNTY", "STATE", "STATEABBRV", "NRI_VER", *FREQUENCY_FIELDS)


@dataclass(frozen=True)
class NriCounty:
    county_fips: str  # five digits: state then county, for example "48113"
    county_name: str
    state_name: str
    state: str  # two-letter code
    release: str  # FEMA's name for the data release, for example "December 2025"
    frequencies: dict[str, float | None]  # None where FEMA gives no figure for the county

    @property
    def county_ugc(self) -> str:
        """The same county as the Weather Service writes it, for example "TXC113"."""
        return f"{self.state}C{self.county_fips[2:]}"


def request_params(lat: float, lon: float) -> dict[str, str]:
    """Query parameters for "the county whose area contains this point"."""
    lat, lon = checked_point(lat, lon)
    return {
        "geometry": f"{lon!r},{lat!r}",  # this service wants longitude first
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": ",".join(OUT_FIELDS),
        "returnGeometry": "false",
        "f": "json",
    }


def parse_county(payload: dict) -> NriCounty:
    if "error" in payload:
        raise SourceError(f"FEMA service error: {payload['error']}")
    features = payload.get("features")
    if not isinstance(features, list) or len(features) != 1:
        found = len(features) if isinstance(features, list) else "no feature list"
        raise SourceError(f"expected exactly one county at the point, got {found}")
    row = features[0]["attributes"]
    fips = row["STCOFIPS"]
    if not (isinstance(fips, str) and len(fips) == 5 and fips.isdigit()):
        raise SourceError(f"unexpected county code {fips!r}")
    return NriCounty(
        county_fips=fips,
        county_name=row["COUNTY"],
        state_name=row["STATE"],
        state=row["STATEABBRV"],
        release=row["NRI_VER"],
        frequencies={field: row[field] for field in FREQUENCY_FIELDS},
    )
