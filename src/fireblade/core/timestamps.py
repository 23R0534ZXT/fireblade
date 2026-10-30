"""Presentation only. Source precision and timezone text are never rewritten."""

import re
from datetime import datetime

_ISO = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d+))?((?:Z|[+-]\d{2}:?\d{2})?)$"
)


def display_timestamp(value, mode="source"):
    if mode == "source":
        return value
    match = _ISO.fullmatch(value.strip())
    if not match:
        return value
    try:
        datetime.fromisoformat(value.strip())
    except ValueError:
        return value
    date, clock, fraction, zone = match.groups()
    if mode == "iso7":
        # Never remove precision greater than seven source digits.
        fraction = (fraction or "").ljust(7, "0")
    return date + " " + clock + ("." + fraction if fraction else "") + zone


def timestamp_key(column):
    """UTC nanosecond order key, including dates outside TIMESTAMP_NS's range."""
    return (
        f"cast(epoch_us(try_cast({column} AS TIMESTAMPTZ)) AS HUGEINT)*1000 + "
        f"try_cast(right(rpad(regexp_extract({column}, '\\.([0-9]+)',1),9,'0'),3) AS HUGEINT)"
    )


from functools import lru_cache
import calendar

_PATTERN = re.compile(
    r"'[^']*'|\"[^\"]*\"|\\.|yyyy|yyy|yy|y|MMMM|MMM|MM|M|dddd|ddd|dd|d|HH|H|hh|h|mm|m|ss|s|f{1,9}|F{1,9}|zzz|zz|z|K|tt|t|[^A-Za-z\\'\"]+"
)


@lru_cache(maxsize=64)
def date_pattern(pattern):
    if not isinstance(pattern, str) or not 1 <= len(pattern) <= 256:
        raise ValueError("Format de date limité à 256 caractères")
    pattern = {
        "o": "yyyy-MM-dd'T'HH:mm:ss.fffffffK",
        "O": "yyyy-MM-dd'T'HH:mm:ss.fffffffK",
        "s": "yyyy-MM-dd'T'HH:mm:ss",
    }.get(pattern, pattern)
    tokens = []
    at = 0
    while at < len(pattern):
        match = _PATTERN.match(pattern, at)
        if not match:
            raise ValueError(
                f"Jeton de format de date non traduit au caractère {at + 1}"
            )
        tokens.append(match.group())
        at = match.end()
    return tuple(tokens)


def format_timestamp(value, pattern):
    match = _ISO.fullmatch(value.strip())
    if not match:
        return value
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError:
        return value
    _date, _clock, fraction, zone = match.groups()
    fraction = fraction or ""
    offset = zone if zone and zone != "Z" else "+00:00"
    if len(offset) == 5:
        offset = offset[:3] + ":" + offset[3:]
    fields = {
        "yyyy": f"{dt.year:04}",
        "yyy": f"{dt.year:03}",
        "yy": f"{dt.year % 100:02}",
        "y": str(dt.year % 100),
        "MMMM": calendar.month_name[dt.month],
        "MMM": calendar.month_abbr[dt.month],
        "MM": f"{dt.month:02}",
        "M": str(dt.month),
        "dddd": calendar.day_name[dt.weekday()],
        "ddd": calendar.day_abbr[dt.weekday()],
        "dd": f"{dt.day:02}",
        "d": str(dt.day),
        "HH": f"{dt.hour:02}",
        "H": str(dt.hour),
        "hh": f"{dt.hour % 12 or 12:02}",
        "h": str(dt.hour % 12 or 12),
        "mm": f"{dt.minute:02}",
        "m": str(dt.minute),
        "ss": f"{dt.second:02}",
        "s": str(dt.second),
        "zzz": offset,
        "zz": offset[:3],
        "z": offset[0] + str(int(offset[1:3])),
        "K": zone,
        "tt": "AM" if dt.hour < 12 else "PM",
        "t": "A" if dt.hour < 12 else "P",
    }
    result = []
    for token in date_pattern(pattern):
        if token in fields:
            result.append(fields[token] or "")
        elif token[0] in ("f", "F"):
            # The seven-digit forensic display must not hide finer source data.
            size = max(len(token), len(fraction)) if len(token) >= 7 else len(token)
            text = fraction.ljust(size, "0")[:size]
            result.append(text.rstrip("0") if token[0] == "F" else text)
        elif token[0] in ("'", '"'):
            result.append(token[1:-1])
        elif token[0] == "\\":
            result.append(token[1:])
        else:
            result.append(token)
    return "".join(result)
