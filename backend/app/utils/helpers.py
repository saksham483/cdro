import hashlib
import json
from datetime import datetime, timezone

def calculate_sha256(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def serialize_utc(dt) -> str | None:
    """
    Serializes a datetime as an ISO-8601 UTC string with an explicit 'Z' suffix.

    SQLite has no timezone-aware DateTime storage: SQLAlchemy strips tzinfo on
    read-back, so naive datetimes coming out of the DB must be assumed to be UTC.
    The explicit 'Z' suffix is required so frontend `new Date(...)` parses the
    value as UTC instead of the browser's local timezone.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")
