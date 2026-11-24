"""Command-line entry point.

Subcommands are added one milestone at a time (docs/PLAN.md, section 13).
So far: ingest, data-report. To come: rank, ask, eval, serve.
"""

import argparse
import sys

from wra import __version__, paths
from wra.hubs import load_hubs
from wra.ingest.errors import SourceError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wra", description="Weather Risk Intelligence Agent")
    parser.add_argument("--version", action="version", version=f"wra {__version__}")
    commands = parser.add_subparsers(dest="command")

    ingest = commands.add_parser(
        "ingest",
        help="build the database from the stored raw responses (no network)",
        description="Build data/wra.sqlite from the raw responses under data/raw. Uses no network "
        "unless --refresh is given.",
    )
    ingest.add_argument(
        "--refresh", action="store_true", help="fetch every response again from the public services first"
    )
    commands.add_parser("data-report", help="print what the database holds, hub by hub")

    args = parser.parse_args(argv)
    try:
        if args.command == "ingest":
            return _ingest(args.refresh)
        if args.command == "data-report":
            return _data_report()
    except SourceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    parser.print_help()
    return 0


def _ingest(refresh_first: bool) -> int:
    from wra.ingest.build import build_database

    hubs = load_hubs(paths.hubs_config())
    if refresh_first:
        from wra.ingest.fetch import refresh

        print(f"Fetching 4 responses for each of {len(hubs)} hubs, one second apart ...", flush=True)
        refresh(hubs, paths.raw_dir())
    loaded = build_database(hubs, paths.raw_dir(), paths.database())

    header = ["hub", "station days", "FEMA figures", "zone rows", "polygon rows", "skipped"]
    rows = [
        [
            data.hub.id,
            len(data.days),
            sum(1 for value in data.county.frequencies.values() if value is not None),
            len(data.zone.events),
            len(data.polygon.events),
            len(data.zone.skipped) + len(data.polygon.skipped),
        ]
        for data in loaded
    ]
    rows.append(["all"] + [sum(row[i] for row in rows) for i in range(1, len(header))])
    widths = [max(len(str(row[i])) for row in [header] + rows) for i in range(len(header))]
    for row in [header] + rows:
        print("  ".join(str(value).ljust(width) for value, width in zip(row, widths)).rstrip())
    source = "fetched just now" if refresh_first else "stored raw responses, no network used"
    print("\nRows are warnings, watches and advisories of every type; scoring picks the ones it counts.")
    print(f"Built {paths.database()} from {source}.")
    return 0


def _data_report() -> int:
    from wra.ingest.report import data_report

    text, ok = data_report(paths.database(), paths.raw_dir())
    print(text)
    return 0 if ok else 1
