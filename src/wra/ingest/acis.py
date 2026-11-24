"""NOAA station observations through the ACIS web service: measured daily snowfall and rain.

Values arrive as text. A number is inches. "T" is a trace: something fell but
too little to measure. "M" is missing: nobody knows. The three are kept apart,
because "0.0", "a trace" and "unknown" are different answers to "did it snow?".

Like FEMA's service, this one reports an error with HTTP 200 and an error body.
"""

import re
from dataclasses import dataclass
from datetime import date

from wra.ingest.errors import SourceError

DATA_URL = "https://data.rcc-acis.org/StnData"

_NUMBER = re.compile(r"\d+(\.\d+)?")


@dataclass(frozen=True)
class Station:
    name: str
    state: str
    lat: float
    lon: float
    county_fips: str
    utc_offset_hours: float  # the station's standard-time offset, for example -6.0
    ids: tuple[str, ...]


@dataclass(frozen=True)
class DailyObs:
    day: date
    snow_in: float | None  # None when missing
    snow_flag: str  # "" measured, "T" trace, "M" missing
    precip_in: float | None
    precip_flag: str


def request_params(station_id: str, start: date, end: date) -> dict[str, str]:
    if not station_id:
        raise ValueError("station id is empty")
    return {
        "sid": station_id,
        "sdate": start.isoformat(),
        "edate": end.isoformat(),
        "elems": "snow,pcpn",
        "meta": "name,state,sids,ll,county,tzo",
        "output": "json",
    }


def parse_station(payload: dict, station_id: str) -> tuple[Station, list[DailyObs]]:
    """Read one station's metadata and days, checking it is the station we asked for."""
    if "error" in payload:
        raise SourceError(f"station service error for {station_id}: {payload['error']}")
    meta = payload["meta"]
    ids = tuple(entry.split()[0] for entry in meta["sids"])
    if station_id not in ids:
        raise SourceError(f"response is for a different station: asked {station_id}, got ids {ids}")
    lon, lat = meta["ll"]  # this service lists longitude first
    station = Station(
        name=meta["name"],
        state=meta["state"],
        lat=lat,
        lon=lon,
        county_fips=meta["county"],
        utc_offset_hours=meta["tzo"],
        ids=ids,
    )
    days = []
    for day_text, snow_text, precip_text in payload["data"]:
        snow, snow_flag = _value(snow_text)
        precip, precip_flag = _value(precip_text)
        days.append(DailyObs(date.fromisoformat(day_text), snow, snow_flag, precip, precip_flag))
    return station, days


def _value(text: str) -> tuple[float | None, str]:
    if text == "M":
        return None, "M"
    if text == "T":
        return 0.0, "T"
    if _NUMBER.fullmatch(text):
        return float(text), ""
    raise SourceError(f"station value {text!r} is not a number, T or M")
