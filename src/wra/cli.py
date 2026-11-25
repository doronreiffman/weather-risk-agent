"""Command-line entry point.

Subcommands, added one milestone at a time (docs/PLAN.md, section 13):
ingest, data-report, rank, ask, chat, eval, serve, alert.
"""

import argparse
import sys
from pathlib import Path

from wra import __version__, paths
from wra.hubs import load_hubs
from wra.ingest.errors import SourceError
from wra.stored import NoDatabase


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

    rank = commands.add_parser(
        "rank",
        help="rank the hubs by expected disruption days a year (no network)",
        description="Print the official ranking for one hazard or overall, as the rank_hubs tool returns it.",
    )
    rank.add_argument("hazard", choices=["overall", "winter", "flood", "severe_storm", "hurricane"])
    rank.add_argument("--region", choices=["all", "midwest", "south", "west"], default="all")
    rank.add_argument("--top", type=int, default=None, metavar="N", help="show only the top N hubs")

    ask = commands.add_parser(
        "ask",
        help="ask the agent one question (a paid API call)",
        description="Send one question to the agent and print its validated answer, the tables and the "
        "data, period and confidence lines. Needs ANTHROPIC_API_KEY in .env.",
    )
    ask.add_argument("question")
    commands.add_parser(
        "chat",
        help="a conversation with the agent in the terminal, follow-ups included (paid API calls)",
        description="Type questions; each answer is validated before it is printed. An empty line or Ctrl-D ends.",
    )

    evaluate = commands.add_parser(
        "eval",
        help="run the fourteen evaluation cases through an agent and print the score",
        description="Run every evaluation case, grade the answers in code, print a table and a score, and save "
        "every conversation under evals/runs/. The clock is pinned to 2026-11-24.",
    )
    evaluate.add_argument("--agent", choices=["claude", "stub"], default="claude",
                          help="claude: the real agent, paid API calls (default); stub: answers nothing")
    evaluate.add_argument("--reps", type=int, default=1, metavar="N", help="repetitions per case (default 1)")
    evaluate.add_argument("--require-target", action="store_true",
                          help="exit with status 1 when the plan's target is missed (used by scripts/e2e.sh)")

    serve = commands.add_parser(
        "serve",
        help="run the chat page and its API (each question is a paid API call)",
        description="Serve the chat page at / and the API under /api from one process; conversations live in "
        "memory until the server stops. Needs ANTHROPIC_API_KEY in .env.",
    )
    serve.add_argument("--host", default="127.0.0.1",
                       help="address to listen on (default 127.0.0.1: this machine only, so nobody else can spend "
                            "the API credit). Any other address is public mode: it needs WRA_ACCESS_CODE, asks for "
                            "sign-in and caps questions a day")  # fmt: skip
    serve.add_argument("--port", type=int, default=8000, help="port to listen on (default 8000)")

    alert = commands.add_parser(
        "alert",
        help="compare today's ranking with the last reviewed one: no network, no model",
        description="Compare the overall ranking with the reviewed copy in data/reviewed_scores.json and print "
        "'No change' or the alert's title and body (docs/ALERT_DESIGN.md). The weekly GitHub job runs it after a "
        "fresh fetch and opens an issue on a change.",
    )
    alert.add_argument("--accept", action="store_true",
                       help="save today's ranking as the reviewed one; commit it with the change that caused it")
    alert.add_argument("--demo", action="store_true",
                       help="compare with the hurricane weight doubled instead: a labelled demonstration")
    alert.add_argument("--out", type=Path, default=None, metavar="DIR",
                       help="also write the result for the GitHub job: result, title.txt, body.md, change_id")  # fmt: skip

    args = parser.parse_args(argv)
    try:
        if args.command == "ingest":
            return _ingest(args.refresh)
        if args.command == "data-report":
            return _data_report()
        if args.command == "rank":
            return _rank(args.hazard, args.region, args.top)
        if args.command == "ask":
            return _ask(args.question)
        if args.command == "chat":
            return _chat()
        if args.command == "eval":
            return _eval(args.agent, args.reps, args.require_target)
        if args.command == "serve":
            return _serve(args.host, args.port)
        if args.command == "alert":
            return _alert(args.accept, args.demo, args.out)
    except (SourceError, NoDatabase) as error:
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


def _rank(hazard: str, region: str, top: int | None) -> int:
    from wra.tools.context import load_context
    from wra.tools.registry import run_tool
    from wra.tools.text import as_text

    args = {"hazard": hazard, "region": region, "top_n": top, "weight_changes": []}
    result = run_tool(load_context(), "rank_hubs", args)
    print(as_text(result))
    return 0 if result.ok else 1


def _eval(agent_name: str, reps: int, require_target: bool = False) -> int:
    from wra.evals.cases import CASES
    from wra.evals.run import StubAgent, pinned_context, report, run_eval, target_met
    from wra.tools.context import load_context

    ctx = pinned_context(load_context())  # the agent's tools and the graders share the pinned date
    if agent_name == "stub":
        agent = StubAgent()
    else:
        from wra.agent.loop import ClaudeAgent

        agent = ClaudeAgent(ctx)
    runs, out_dir = run_eval(agent, ctx, reps=reps, out_root=paths.root() / "evals" / "runs")
    print(report(runs, len(CASES), reps))
    print(f"Saved every conversation and check to {out_dir}.")
    return 1 if require_target and not target_met(runs)[0] else 0


def _ask(question: str) -> int:
    from wra.agent.loop import ClaudeAgent
    from wra.tools.context import load_context

    reply = ClaudeAgent(load_context()).answer(None, question)
    _print_reply(reply)
    return 1 if reply.status == "error" else 0


def _chat() -> int:
    from wra.agent.loop import ClaudeAgent
    from wra.tools.context import load_context

    agent, session = ClaudeAgent(load_context()), None
    print("Ask about the hubs' weather exposure. An empty line ends.")
    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            break
        if not question:
            break
        reply = agent.answer(session, question)
        session = reply.session_id
        _print_reply(reply)
    return 0


def _serve(host: str, port: int) -> int:
    import uvicorn

    from wra.agent.limits import DailyLimit
    from wra.agent.loop import ClaudeAgent
    from wra.agent.settings import load_settings
    from wra.api.app import create_app
    from wra.api.public import access_code_from_env, is_public
    from wra.tools.context import load_context

    public = is_public(host)
    code = access_code_from_env() if public else None
    if public and code is None:  # fail closed: a missing secret stops the deploy instead of opening the site
        print(f"error: listening on {host} makes the server public, and WRA_ACCESS_CODE is not set. Set it, or "
              "listen on 127.0.0.1.", file=sys.stderr)  # fmt: skip
        return 2

    ctx = load_context()
    settings = load_settings()
    admit = DailyLimit(settings.daily_question_limit).admit if public else None
    agent = ClaudeAgent(ctx, settings, admit=admit)  # one agent for the process: every conversation lives in it
    app = create_app(agent, ctx, access_code=code)
    print(f"Chat page at http://{host}:{port}/ . Each question is a paid API call. Ctrl-C stops the server.",
          flush=True)  # fmt: skip
    if public:
        print(f"Public mode: sign-in required, at most {settings.daily_question_limit} questions a day.", flush=True)
    uvicorn.run(app, host=host, port=port)
    return 0


def _alert(accept: bool, demo: bool, out: Path | None) -> int:
    """The score-change alert (docs/ALERT_DESIGN.md 5.3). Exit 0 for "no change" and for a change; anything that
    could not compare exits non-zero and writes no result, so a failure never reads as "no change"."""
    from wra.alert import DEMO_CHANGES, change_id, compare, current_snapshot, from_json, message, to_json
    from wra.scoring.config import HAZARDS
    from wra.tools.context import load_context

    if accept and demo:
        print("error: --accept and --demo cannot be used together.", file=sys.stderr)
        return 2
    saved_path = paths.reviewed_scores()
    shown = saved_path.relative_to(paths.root())
    ctx = load_context()  # a missing database raises NoDatabase, which main turns into an error line
    if accept:
        saved_path.write_text(to_json(current_snapshot(ctx)))
        print(f"Saved today's ranking as the reviewed one: {shown}. Commit it with the change that caused it.")
        return 0
    if not saved_path.exists():
        print(f'error: no reviewed ranking at {shown}. Run "uv run wra alert --accept" once the ranking is reviewed.',
              file=sys.stderr)  # fmt: skip
        return 1
    try:
        saved = from_json(saved_path.read_text())
    except ValueError as error:
        print(f"error: the reviewed ranking at {shown} cannot be read ({error}).", file=sys.stderr)
        return 1

    diff = compare(saved, current_snapshot(ctx, DEMO_CHANGES if demo else None))
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
    if diff.is_empty:
        print(f"No change since the ranking was last reviewed (data as of {saved.inputs.get('data_as_of')}).")
        if out is not None:
            (out / "result").write_text("no_change\n")
        return 0
    title, body = message(diff, {h: ctx.config.hazards[h].label for h in HAZARDS}, demo)
    print(f"{title}\n\n{body}", end="")
    if out is not None:
        (out / "title.txt").write_text(title + "\n")
        (out / "body.md").write_text(body)
        (out / "change_id").write_text(change_id(diff, demo) + "\n")
        (out / "result").write_text("change\n")  # written last: "change" only once the files it names exist
    return 0


def _print_reply(reply) -> None:
    from wra.tools.text import display_text, footnote_text

    t = reply.trace
    if reply.status == "error":
        print(f"error: {reply.error}", file=sys.stderr)
    else:
        print(f"[{reply.status}{', what-if' if reply.is_what_if else ''}] {reply.verdict}")
        for caveat in reply.caveats:
            print(f"  - {caveat}")
        for table in reply.tables:
            print("\n" + display_text(table))
        if reply.footnote:
            print("\n" + footnote_text(reply.footnote))
    calls = ", ".join(f"{c.id} {c.name}" for c in t.tool_calls) or "none"
    cost = t.usage.get("cost_usd")
    print(f"\n(model {t.model}; tool calls: {calls}; repaired: {'yes' if t.repaired else 'no'}; "
          f"{t.latency_ms / 1000:.1f} s; tokens {_input_tokens(t.usage)} in "
          f"({t.usage.get('cache_read_input_tokens', 0)} from cache), {t.usage.get('output_tokens', 0)} out"
          + (f"; cost ${cost:.4f} at list price" if cost is not None else "") + ")")


def _input_tokens(usage: dict) -> int:
    """All input tokens: the API reports uncached, cache-read and cache-write input separately."""
    return sum(usage.get(k, 0) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
