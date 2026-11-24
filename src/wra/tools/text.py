"""A tool result as plain text, for the command line: the table, its notes and the footnote."""

from wra.tools.envelope import SOURCE_NAMES, Display, ToolResult


def as_text(result: ToolResult) -> str:
    if not result.ok:
        return f"{result.tool}: {result.error.code}: {result.error.message}"
    return "\n".join([display_text(result.display), "", footnote_text(result.provenance)])


def display_text(d: Display) -> str:
    cells = [d.columns] + [[cell_text(c) for c in row] for row in d.rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(d.columns))]
    lines = [d.title, ""]
    for n, row in enumerate(cells):
        lines.append("  ".join(value.ljust(width) for value, width in zip(row, widths)).rstrip())
        if n == 0:
            lines.append("  ".join("-" * width for width in widths))
    lines += ["", d.what_counts]
    lines += [f"Note: {note}" for note in d.notes]
    return "\n".join(lines)


def footnote_text(p) -> str:
    """The data, period and confidence lines, for a tool's provenance or an answer's footnote."""
    return "\n".join([
        f"Data: {'; '.join(SOURCE_NAMES[s] for s in p.sources)}. Period: {p.period}. Data as of {p.data_as_of}.",
        f"Confidence: {p.confidence}. {p.confidence_reason}",
    ])  # fmt: skip


def cell_text(value) -> str:
    """Figures as the tool gives them, padded to two decimals: 2.9 shows as 2.90, FEMA's 0.0115 stays 0.0115.
    The command line and the chat page both show cells this way; an empty cell is blank."""
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}" if round(value, 2) == value else str(value)
    return str(value)
