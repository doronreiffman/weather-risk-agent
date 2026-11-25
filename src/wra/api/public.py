"""Public mode (docs/DEPLOY_DESIGN.md 5.1 and 5.2).

The server is public when it listens on any address but this machine's own. Then it needs an access code
(WRA_ACCESS_CODE) or refuses to start, so a deploy with a missing secret fails instead of opening the site,
and every route but /healthz sits behind HTTP Basic sign-in: the username `analyst`, the code as password.
The browser shows its own sign-in box and sends the same credentials with the page's calls to /api, so the
page itself does not change.
"""

import base64
import binascii
import os
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

USERNAME = "analyst"
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
OPEN_PATHS = frozenset({"/healthz"})  # no model call; the host checks the server is up with it
SIGN_IN = {"WWW-Authenticate": 'Basic realm="Weather Risk Agent", charset="UTF-8"'}


def is_public(host: str) -> bool:
    return host not in LOCAL_HOSTS


def access_code_from_env() -> str | None:
    """WRA_ACCESS_CODE without surrounding spaces; unset or blank counts as missing."""
    return (os.environ.get("WRA_ACCESS_CODE") or "").strip() or None


def credentials_ok(header: str | None, access_code: str) -> bool:
    """Whether an Authorization header carries `analyst` and the access code. Anything malformed is a no."""
    scheme, _, encoded = (header or "").partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        pair = base64.b64decode(encoded.strip(), validate=True).decode("utf-8")
    except (binascii.Error, ValueError):  # not base64, or not UTF-8 (UnicodeDecodeError is a ValueError)
        return False
    username, colon, code = pair.partition(":")  # at the first colon, so a code may hold one
    if not colon:
        return False
    # both compared, as bytes: compare_digest takes ASCII-only text, and a code may not be ASCII
    user_ok = secrets.compare_digest(username.encode("utf-8"), USERNAME.encode("utf-8"))
    code_ok = secrets.compare_digest(code.encode("utf-8"), access_code.encode("utf-8"))
    return user_ok and code_ok


def add_door(app: FastAPI, access_code: str) -> None:
    @app.middleware("http")
    async def door(request: Request, call_next):
        if request.url.path in OPEN_PATHS or credentials_ok(request.headers.get("authorization"), access_code):
            return await call_next(request)
        return JSONResponse({"detail": f"Sign in with the username {USERNAME} and the access code."},
                            status_code=401, headers=SIGN_IN)  # fmt: skip
