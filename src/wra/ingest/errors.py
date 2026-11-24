"""The one error the ingest raises when a source's answer cannot be trusted."""


class SourceError(Exception):
    """A response is an error, is for the wrong place, or has a value we do not understand.

    Raised instead of guessing. The ingest stops and the stored data stays as it was.
    """
