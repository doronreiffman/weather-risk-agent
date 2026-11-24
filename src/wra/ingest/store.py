"""The SQLite database: its tables and the one function that writes them (docs/PLAN.md, section 12).

The file is rebuilt from scratch each time and swapped into place at the end,
so a failed build leaves the previous database untouched.

Raw warning rows are stored, not totals. Time under warning is computed from
them by the scoring code, so the counting rule lives in one tested place and
any figure can be traced back to individual warnings.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wra.ingest.build import HubData

SCHEMA = """
CREATE TABLE hubs (
    hub_id               TEXT PRIMARY KEY,
    city                 TEXT NOT NULL,
    state                TEXT NOT NULL,
    region               TEXT NOT NULL,
    tz                   TEXT NOT NULL,
    station_id           TEXT NOT NULL,
    station_name         TEXT NOT NULL,   -- from the station service
    lat                  REAL NOT NULL,   -- from the station service
    lon                  REAL NOT NULL,
    county_fips          TEXT NOT NULL,   -- from FEMA: the county containing the point
    county_name          TEXT NOT NULL,
    station_county_fips  TEXT NOT NULL,   -- the county the station service names
    warning_county_codes TEXT NOT NULL,   -- as the warning archive names it, comma-separated
    warning_zone_codes   TEXT NOT NULL,   -- forecast zones, comma-separated
    county_check         TEXT NOT NULL    -- 'agree' when FEMA and the warning archive name one county
);

-- One row per spell of a warning, watch or advisory at the hub. All types are
-- kept; the scoring config decides which count.
CREATE TABLE warning_events (
    hub_id       TEXT NOT NULL REFERENCES hubs,
    matched_by   TEXT NOT NULL,           -- 'zone' or 'polygon'
    wfo          TEXT NOT NULL,           -- issuing forecast office
    vtec_year    INTEGER NOT NULL,
    phenomena    TEXT NOT NULL,           -- type code, for example WS
    significance TEXT NOT NULL,           -- W warning, A watch, Y advisory
    event_id     INTEGER NOT NULL,
    ugc          TEXT,                    -- county or zone code; NULL for a polygon match
    issue_utc    TEXT NOT NULL,           -- 2021-02-13T12:00:00Z
    expire_utc   TEXT NOT NULL,
    name         TEXT NOT NULL
);
CREATE INDEX warning_events_by_type ON warning_events (hub_id, phenomena, significance);

CREATE TABLE fema_nri (
    hub_id      TEXT NOT NULL REFERENCES hubs,
    county_fips TEXT NOT NULL,
    release     TEXT NOT NULL,            -- FEMA's release name
    field       TEXT NOT NULL,            -- FEMA's field name, for example HRCN_AFREQ
    value       REAL,                     -- NULL where FEMA gives no figure
    PRIMARY KEY (hub_id, field)
);

CREATE TABLE station_daily (
    hub_id      TEXT NOT NULL REFERENCES hubs,
    day         TEXT NOT NULL,            -- 2025-02-27
    snow_in     REAL,                     -- inches; NULL when missing
    snow_flag   TEXT NOT NULL,            -- '' measured, 'T' trace, 'M' missing
    precip_in   REAL,
    precip_flag TEXT NOT NULL,
    PRIMARY KEY (hub_id, day)
);

CREATE TABLE fetch_log (
    source     TEXT NOT NULL,
    hub_id     TEXT NOT NULL REFERENCES hubs,
    url        TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    sha256     TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    PRIMARY KEY (source, hub_id)
);

-- Source records left out, each with the reason and the record itself.
CREATE TABLE skipped_records (
    hub_id      TEXT NOT NULL REFERENCES hubs,
    source      TEXT NOT NULL,
    reason      TEXT NOT NULL,
    record_json TEXT NOT NULL
);

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def write_database(db_path: Path, loaded: list[HubData], meta: dict[str, str]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    staging = db_path.with_name(db_path.name + ".new")
    staging.unlink(missing_ok=True)
    try:
        connection = sqlite3.connect(staging)
        try:
            with connection:
                connection.executescript(SCHEMA)
                connection.executemany("INSERT INTO meta VALUES (?, ?)", sorted(meta.items()))
                for data in loaded:
                    _write_hub(connection, data)
        finally:
            connection.close()
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    os.replace(staging, db_path)


def _write_hub(connection: sqlite3.Connection, data: HubData) -> None:
    hub, station, county = data.hub, data.station, data.county
    connection.execute(
        "INSERT INTO hubs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            hub.id, hub.city, hub.state, hub.region, hub.tz, hub.station, station.name,
            station.lat, station.lon, county.county_fips, county.county_name, station.county_fips,
            ",".join(data.county_codes), ",".join(data.zone_codes), data.county_check,
        ),
    )  # fmt: skip
    for source, parsed in (("iem_zone", data.zone), ("iem_polygon", data.polygon)):
        connection.executemany(
            "INSERT INTO warning_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    hub.id, e.matched_by, e.wfo, e.vtec_year, e.phenomena, e.significance, e.event_id,
                    e.ugc, _utc_text(e.issue_utc), _utc_text(e.expire_utc), e.name,
                )
                for e in parsed.events
            ],
        )  # fmt: skip
        connection.executemany(
            "INSERT INTO skipped_records VALUES (?, ?, ?, ?)",
            [(hub.id, source, s.reason, json.dumps(s.record, sort_keys=True)) for s in parsed.skipped],
        )
    connection.executemany(
        "INSERT INTO fema_nri VALUES (?, ?, ?, ?, ?)",
        [(hub.id, county.county_fips, county.release, field, value) for field, value in county.frequencies.items()],
    )
    connection.executemany(
        "INSERT INTO station_daily VALUES (?, ?, ?, ?, ?, ?)",
        [(hub.id, d.day.isoformat(), d.snow_in, d.snow_flag, d.precip_in, d.precip_flag) for d in data.days],
    )
    connection.executemany(
        "INSERT INTO fetch_log VALUES (?, ?, ?, ?, ?, ?)",
        [(f.source, f.hub_id, f.url, f.fetched_at, f.sha256, f.size_bytes) for f in data.fetches],
    )


def _utc_text(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
