"""Command-line entry point.

Subcommands (ingest, data-report, rank, ask, eval, serve) are added one
milestone at a time; see docs/PLAN.md, section 13.
"""

import argparse

from wra import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wra", description="Weather Risk Intelligence Agent"
    )
    parser.add_argument("--version", action="version", version=f"wra {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
