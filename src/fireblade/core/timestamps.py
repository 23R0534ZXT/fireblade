"""Presentation only. Source precision and timezone text are never rewritten."""
import re
from datetime import datetime

_ISO = re.compile(r'^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d+))?((?:Z|[+-]\d{2}:?\d{2})?)$')


def display_timestamp(value, mode='source'):
    if mode == 'source':
        return value
    match = _ISO.fullmatch(value.strip())
    if not match:
        return value
    try:
        datetime.fromisoformat(value.strip())
    except ValueError:
        return value
    date, clock, fraction, zone = match.groups()
    if mode == 'iso7':
        # Never remove precision greater than seven source digits.
        fraction = (fraction or '').ljust(7, '0')
    return date + ' ' + clock + ('.' + fraction if fraction else '') + zone


def timestamp_key(column):
    """UTC nanosecond order key, including dates outside TIMESTAMP_NS's range."""
    return (f"cast(epoch_us(try_cast({column} AS TIMESTAMPTZ)) AS HUGEINT)*1000 + "
            f"try_cast(right(rpad(regexp_extract({column}, '\\.([0-9]+)',1),9,'0'),3) AS HUGEINT)")
