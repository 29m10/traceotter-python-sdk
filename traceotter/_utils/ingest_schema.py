from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Mapping, MutableMapping, Optional


RawSpan = Dict[str, Any]


class ErrorCode(str, enum.Enum):
    INVALID_SPAN = "INVALID_SPAN"
    MISSING_TRACE_ID = "MISSING_TRACE_ID"
    MISSING_SPAN_ID = "MISSING_SPAN_ID"
    INVALID_START_TIME = "INVALID_START_TIME"
    INVALID_ATTRIBUTES = "INVALID_ATTRIBUTES"


@dataclass
class SchemaValidationError(Exception):
    code: ErrorCode
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.message}"


def _extract_from_locations(
    span: Mapping[str, Any],
    *,
    keys: Mapping[str, str],
) -> Optional[Any]:
    """
    Helper to look up a value across multiple possible locations.

    `keys` maps logical field names ('root', 'context', 'attributes') to the
    actual key that should be checked in that container.
    """

    # top-level
    root_key = keys.get("root")
    if root_key is not None and root_key in span:
        return span.get(root_key)

    # context.*
    context_key = keys.get("context")
    if context_key is not None:
        context = span.get("context")
        if isinstance(context, Mapping) and context_key in context:
            return context.get(context_key)

    # attributes.*
    attributes_key = keys.get("attributes")
    if attributes_key is not None:
        attributes = span.get("attributes")
        if isinstance(attributes, Mapping) and attributes_key in attributes:
            return attributes.get(attributes_key)

    return None


def _parse_start_time(value: Any) -> float:
    """
    Parse start_time/startTime according to the schema rules:

    - Numbers are accepted as-is (interpreted as Unix seconds or ms downstream)
    - Strings:
      * If parseable as float, use directly
      * Otherwise interpreted as ISO 8601 and converted to UTC timestamp
    """
    # Numeric types
    if isinstance(value, (int, float)):
        return float(value)

    # String types
    if isinstance(value, str):
        # Try numeric string first
        try:
            return float(value)
        except ValueError:
            pass

        # Fallback to ISO 8601
        try:
            # Support trailing "Z" by normalizing to +00:00
            if value.endswith("Z"):
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(value)
            return dt.timestamp()
        except Exception as exc:  # pragma: no cover - defensive
            raise SchemaValidationError(
                ErrorCode.INVALID_START_TIME,
                f"Unparseable ISO 8601 start_time value: {value!r} ({exc})",
            )

    raise SchemaValidationError(
        ErrorCode.INVALID_START_TIME,
        f"Unsupported start_time type: {type(value).__name__}",
    )


def validate_span_schema(span: Any) -> RawSpan:
    """
    Validate and normalize a RawSpan according to the v1/ingest schema.

    Rules (mirroring the ingestion service):

    - span must be a JSON object (dict), otherwise INVALID_SPAN
    - trace_id is required, taken from one of:
        * span['trace_id']
        * span['context']['trace_id']
        * span['attributes']['trace_id']
      If missing or falsy -> MISSING_TRACE_ID
    - span_id is required, taken from one of:
        * span['span_id']
        * span['id']
        * span['context']['span_id']
        * span['attributes']['span_id']
      If missing or falsy -> MISSING_SPAN_ID
    - start_time/startTime is required, taken from:
        * span['start_time'] or span['startTime']
      Accepted formats:
        * number (int/float)
        * string parseable as float
        * ISO 8601 string
      If missing or unparseable -> INVALID_START_TIME
    - attributes, if present, must be an object/dict, otherwise INVALID_ATTRIBUTES

    On success, returns a shallow-copied dict with normalized fields:
    - 'trace_id'
    - 'span_id'
    - 'start_time' (numeric float)
    and preserves all original keys.
    """
    if not isinstance(span, MutableMapping):
        raise SchemaValidationError(
            ErrorCode.INVALID_SPAN,
            f"Span must be a JSON object/dict, got {type(span).__name__}",
        )

    # Work on a shallow copy so we never mutate caller's data
    normalized: RawSpan = dict(span)

    # Validate attributes type if present
    attributes = normalized.get("attributes")
    if attributes is not None and not isinstance(attributes, MutableMapping):
        raise SchemaValidationError(
            ErrorCode.INVALID_ATTRIBUTES,
            f"'attributes' must be an object/dict, got {type(attributes).__name__}",
        )

    # trace_id resolution
    trace_id = _extract_from_locations(
        normalized,
        keys={
            "root": "trace_id",
            "context": "trace_id",
            "attributes": "trace_id",
        },
    )
    if not trace_id:
        raise SchemaValidationError(
            ErrorCode.MISSING_TRACE_ID,
            "Missing required 'trace_id' (looked in span, context, attributes).",
        )
    normalized["trace_id"] = trace_id

    # span_id resolution
    span_id = _extract_from_locations(
        normalized,
        keys={
            "root": "span_id",
            "context": "span_id",
            "attributes": "span_id",
        },
    )
    if not span_id:
        # Support legacy 'id' as a top-level identifier
        legacy_id = normalized.get("id")
        if legacy_id:
            span_id = legacy_id

    if not span_id:
        raise SchemaValidationError(
            ErrorCode.MISSING_SPAN_ID,
            "Missing required 'span_id' (looked in span_id, id, context, attributes).",
        )
    normalized["span_id"] = span_id

    # start_time / startTime
    raw_start_time = (
        normalized["start_time"]
        if "start_time" in normalized
        else normalized.get("startTime")
    )
    if raw_start_time is None:
        raise SchemaValidationError(
            ErrorCode.INVALID_START_TIME,
            "Missing required 'start_time'/'startTime' field.",
        )

    normalized["start_time"] = _parse_start_time(raw_start_time)

    return normalized

