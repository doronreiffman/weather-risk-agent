"""The coordinate guard: every request for a place goes through `checked_point`.

Why it exists: a request to the warning archive with empty coordinates
returned 926 records and no error (docs/PLAN.md, section 12). Data for the
wrong place looks exactly like data for the right one.
"""

import math

# A box around the contiguous United States, where all the hubs are. It also
# catches a swapped pair: the station service lists longitude first, and
# Miami's coordinates swapped are still a valid point on Earth.
LAT_RANGE = (24.0, 50.0)
LON_RANGE = (-125.0, -66.0)


def checked_point(lat: object, lon: object) -> tuple[float, float]:
    """Return (lat, lon) as floats, or raise ValueError. Never returns a default."""
    for name, value in (("latitude", lat), ("longitude", lon)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a number, got {value!r}")
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"{name} must be a finite number, got {value!r}")
    if not LAT_RANGE[0] <= lat <= LAT_RANGE[1]:
        raise ValueError(f"latitude {lat} is outside the contiguous US {LAT_RANGE}; swapped with longitude?")
    if not LON_RANGE[0] <= lon <= LON_RANGE[1]:
        raise ValueError(f"longitude {lon} is outside the contiguous US {LON_RANGE}; swapped with latitude?")
    return float(lat), float(lon)
