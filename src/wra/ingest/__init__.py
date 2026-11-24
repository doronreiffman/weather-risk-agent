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

# The warning archive's date range, which is wider than the period on purpose.
# Measured 2026-11-24 with narrow requests around known warnings: the service
# keeps a warning when its ISSUE date (UTC) is on or after `sdate` and BEFORE
# `edate`; a warning issued earlier but still in force is not returned. So:
# - start a week early, to catch a warning issued in late December 2015 that
#   was still in force on 1 January 2016 (the longest counted ones run 3 days);
# - end on 2 January 2026, so 31 December 2025 is included, and so is
#   1 January 2026 in UTC, which is still New Year's Eve at every hub.
# Scoring keeps only the hours inside the period, in each hub's time zone.
WARNINGS_ISSUED_FROM = date(2015, 12, 25)
WARNINGS_ISSUED_BEFORE = date(2026, 1, 2)
