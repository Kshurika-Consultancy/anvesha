"""ANV-026: bounded operator policy for retained search data, in seconds."""

import os

DEFAULT_SECONDS = 7 * 24 * 60 * 60
MAX_SECONDS = 365 * 24 * 60 * 60
CLEANUP_BATCH = 100
MAX_BATCH = 500


def validate_seconds(value):
    if type(value) is not int or not 0 <= value <= MAX_SECONDS:
        raise ValueError("retention_seconds must be an integer between 0 and 31536000")
    return value


def seconds_from_env():
    try:
        value = int(os.getenv("ANVESHA_RETENTION_SECONDS", str(DEFAULT_SECONDS)))
    except ValueError:
        raise ValueError("ANVESHA_RETENTION_SECONDS must be an integer") from None
    return validate_seconds(value)
