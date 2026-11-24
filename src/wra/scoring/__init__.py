"""The scoring core: plain Python over stored data, no network and no LLM (docs/PLAN.md, section 5).

- config.py:       the rules in config/scoring.toml, read and checked
- warning_time.py: which warnings count, merged into spells, hours per local year
- kpi.py:          rates, Expected Disruption Days, ranking, bands, what-if weights
- confidence.py:   coverage, separation and weight stability, as a label and a reason
"""
