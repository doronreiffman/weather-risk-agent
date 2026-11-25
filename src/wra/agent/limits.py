"""The public site's cap on questions a day (docs/DEPLOY_DESIGN.md 5.3).

`wra serve` hands `DailyLimit(n).admit` to the agent only in public mode, so `wra ask`, `wra chat` and
`wra eval` never meet it. The count lives in memory: it starts again on a new UTC day, and also whenever the
process restarts (a deploy or a crash). The hard ceiling is the demo workspace's monthly spending limit at
Anthropic.
"""

import threading
from collections.abc import Callable
from datetime import UTC, date, datetime


def utc_today() -> date:
    return datetime.now(UTC).date()


class DailyLimit:
    def __init__(self, limit: int, today: Callable[[], date] = utc_today) -> None:
        self.limit = limit
        self._today = today
        self._lock = threading.Lock()  # the server answers requests on a thread pool
        self._day: date | None = None
        self._count = 0

    def admit(self) -> bool:
        """True and counted if today's limit is not yet used up; False, uncounted, once it is."""
        with self._lock:
            day = self._today()
            if day != self._day:
                self._day, self._count = day, 0
            if self._count >= self.limit:
                return False
            self._count += 1
            return True
