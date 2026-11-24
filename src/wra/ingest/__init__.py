"""Fetching the public data and building the local store (docs/PLAN.md, sections 4 and 12).

Two halves that meet only at the files on disk:

- fetch.py asks the public services and keeps every response as received (raw.py).
- build.py reads those files, checks them, and writes the SQLite database (store.py).
  It has no network code, so the database can be rebuilt offline.
"""

from datetime import date

# The ten full years the score covers (docs/PLAN.md, section 2, answer 4).
PERIOD_START = date(2016, 1, 1)
PERIOD_END = date(2025, 12, 31)
