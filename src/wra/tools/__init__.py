"""The six tools the agent can call (docs/PLAN.md, section 8.1), as plain functions.

Each takes a ToolContext and a validated argument model and returns a ToolResult
(envelope.py). registry.run_tool is the entry point: it validates raw arguments
and turns every refusal into an error result.
"""
