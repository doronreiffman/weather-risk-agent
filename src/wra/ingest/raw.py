"""The raw cache: every response exactly as it was received, and a manifest of where each came from.

Layout: <directory>/<source>/<hub id>.json and <directory>/manifest.json.
The manifest holds the full request address, the time and a checksum, so a
stored file can be traced to its request and a later change to it is noticed.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from wra.ingest.errors import SourceError

SOURCES = ("acis", "fema_nri", "iem_zone", "iem_polygon")
MANIFEST = "manifest.json"


@dataclass(frozen=True)
class FetchRecord:
    source: str
    hub_id: str
    url: str
    fetched_at: str  # UTC, for example "2026-11-24T10:00:00Z"
    sha256: str
    size_bytes: int


class RawStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self._records: dict[tuple[str, str], FetchRecord] = {}
        manifest = directory / MANIFEST
        if manifest.exists():
            for entry in json.loads(manifest.read_text())["fetched"]:
                record = FetchRecord(**entry)
                self._records[(record.source, record.hub_id)] = record

    def save(self, source: str, hub_id: str, url: str, body: bytes, fetched_at: str) -> None:
        path = self._path(source, hub_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        self._records[(source, hub_id)] = FetchRecord(
            source, hub_id, url, fetched_at, hashlib.sha256(body).hexdigest(), len(body)
        )

    def write_manifest(self) -> None:
        entries = [asdict(self._records[key]) for key in sorted(self._records)]
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / MANIFEST).write_text(json.dumps({"fetched": entries}, indent=1) + "\n")

    def load(self, source: str, hub_id: str) -> tuple[dict, FetchRecord]:
        """The stored response as parsed JSON, with its manifest record."""
        record = self._records.get((source, hub_id))
        path = self._path(source, hub_id)
        if record is None or not path.exists():
            raise SourceError(
                f"no stored {source} response for {hub_id} under {self.directory}; "
                "run `wra ingest --refresh` to fetch it"
            )
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != record.sha256:
            raise SourceError(f"{path} has changed since it was fetched (checksum differs from the manifest)")
        return json.loads(body), record

    def _path(self, source: str, hub_id: str) -> Path:
        return self.directory / source / f"{hub_id}.json"
