"""Span attribute management for Traceotter OpenTelemetry integration.

This module defines constants and functions for managing OpenTelemetry span attributes
used by Traceotter. It provides a structured approach to creating and manipulating
attributes for different span types (trace, span, generation) while ensuring consistency.

The module includes:
- Attribute name constants organized by category
- Functions to create attribute dictionaries for different entity types
- Utilities for serializing and processing attribute values
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from traceotter._client.constants import (
    ObservationTypeGenerationLike,
    ObservationTypeSpanLike,
)

from traceotter._utils.serializer import EventSerializer
from traceotter.model import PromptClient
from traceotter.types import MapValue, SpanLevel


class TraceotterOtelSpanAttributes:
    # Traceotter-Trace attributes
    TRACE_NAME = "traceotter.trace.name"
    TRACE_USER_ID = "user.id"
    TRACE_SESSION_ID = "session.id"
    TRACE_TAGS = "traceotter.trace.tags"
    TRACE_PUBLIC = "traceotter.trace.public"
    TRACE_METADATA = "traceotter.trace.metadata"
    TRACE_INPUT = "traceotter.trace.input"
    TRACE_OUTPUT = "traceotter.trace.output"

    # Traceotter-observation attributes
    OBSERVATION_TYPE = "traceotter.observation.type"
    OBSERVATION_METADATA = "traceotter.observation.metadata"
    OBSERVATION_LEVEL = "traceotter.observation.level"
    OBSERVATION_STATUS_MESSAGE = "traceotter.observation.status_message"
    OBSERVATION_INPUT = "traceotter.observation.input"
    OBSERVATION_OUTPUT = "traceotter.observation.output"

    # Traceotter-observation of type Generation attributes
    OBSERVATION_COMPLETION_START_TIME = "traceotter.observation.completion_start_time"
    OBSERVATION_MODEL = "traceotter.observation.model.name"
    OBSERVATION_MODEL_PARAMETERS = "traceotter.observation.model.parameters"
    OBSERVATION_USAGE_DETAILS = "traceotter.observation.usage_details"
    OBSERVATION_COST_DETAILS = "traceotter.observation.cost_details"
    OBSERVATION_PROMPT_NAME = "traceotter.observation.prompt.name"
    OBSERVATION_PROMPT_VERSION = "traceotter.observation.prompt.version"

    # General
    ENVIRONMENT = "traceotter.environment"
    RELEASE = "traceotter.release"
    VERSION = "traceotter.version"

    # Internal
    AS_ROOT = "traceotter.internal.as_root"


def create_trace_attributes(
    *,
    name: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    version: Optional[str] = None,
    release: Optional[str] = None,
    input: Optional[Any] = None,
    output: Optional[Any] = None,
    metadata: Optional[Any] = None,
    tags: Optional[List[str]] = None,
    public: Optional[bool] = None,
) -> dict:
    attributes = {
        TraceotterOtelSpanAttributes.TRACE_NAME: name,
        TraceotterOtelSpanAttributes.TRACE_USER_ID: user_id,
        TraceotterOtelSpanAttributes.TRACE_SESSION_ID: session_id,
        TraceotterOtelSpanAttributes.VERSION: version,
        TraceotterOtelSpanAttributes.RELEASE: release,
        TraceotterOtelSpanAttributes.TRACE_INPUT: _serialize(input),
        TraceotterOtelSpanAttributes.TRACE_OUTPUT: _serialize(output),
        TraceotterOtelSpanAttributes.TRACE_TAGS: tags,
        TraceotterOtelSpanAttributes.TRACE_PUBLIC: public,
        **_flatten_and_serialize_metadata(metadata, "trace"),
    }

    return {k: v for k, v in attributes.items() if v is not None}


def create_span_attributes(
    *,
    metadata: Optional[Any] = None,
    input: Optional[Any] = None,
    output: Optional[Any] = None,
    level: Optional[SpanLevel] = None,
    status_message: Optional[str] = None,
    version: Optional[str] = None,
    observation_type: Optional[
        Union[ObservationTypeSpanLike, Literal["event"]]
    ] = "span",
) -> dict:
    attributes = {
        TraceotterOtelSpanAttributes.OBSERVATION_TYPE: observation_type,
        TraceotterOtelSpanAttributes.OBSERVATION_LEVEL: level,
        TraceotterOtelSpanAttributes.OBSERVATION_STATUS_MESSAGE: status_message,
        TraceotterOtelSpanAttributes.VERSION: version,
        TraceotterOtelSpanAttributes.OBSERVATION_INPUT: _serialize(input),
        TraceotterOtelSpanAttributes.OBSERVATION_OUTPUT: _serialize(output),
        **_flatten_and_serialize_metadata(metadata, "observation"),
    }

    return {k: v for k, v in attributes.items() if v is not None}


def create_generation_attributes(
    *,
    name: Optional[str] = None,
    completion_start_time: Optional[datetime] = None,
    metadata: Optional[Any] = None,
    level: Optional[SpanLevel] = None,
    status_message: Optional[str] = None,
    version: Optional[str] = None,
    model: Optional[str] = None,
    model_parameters: Optional[Dict[str, MapValue]] = None,
    input: Optional[Any] = None,
    output: Optional[Any] = None,
    usage_details: Optional[Dict[str, int]] = None,
    cost_details: Optional[Dict[str, float]] = None,
    prompt: Optional[PromptClient] = None,
    observation_type: Optional[ObservationTypeGenerationLike] = "generation",
) -> dict:
    attributes = {
        TraceotterOtelSpanAttributes.OBSERVATION_TYPE: observation_type,
        TraceotterOtelSpanAttributes.OBSERVATION_LEVEL: level,
        TraceotterOtelSpanAttributes.OBSERVATION_STATUS_MESSAGE: status_message,
        TraceotterOtelSpanAttributes.VERSION: version,
        TraceotterOtelSpanAttributes.OBSERVATION_INPUT: _serialize(input),
        TraceotterOtelSpanAttributes.OBSERVATION_OUTPUT: _serialize(output),
        TraceotterOtelSpanAttributes.OBSERVATION_MODEL: model,
        TraceotterOtelSpanAttributes.OBSERVATION_PROMPT_NAME: prompt.name
        if prompt and not prompt.is_fallback
        else None,
        TraceotterOtelSpanAttributes.OBSERVATION_PROMPT_VERSION: prompt.version
        if prompt and not prompt.is_fallback
        else None,
        TraceotterOtelSpanAttributes.OBSERVATION_USAGE_DETAILS: _serialize(usage_details),
        TraceotterOtelSpanAttributes.OBSERVATION_COST_DETAILS: _serialize(cost_details),
        TraceotterOtelSpanAttributes.OBSERVATION_COMPLETION_START_TIME: _serialize(
            completion_start_time
        ),
        TraceotterOtelSpanAttributes.OBSERVATION_MODEL_PARAMETERS: _serialize(
            model_parameters
        ),
        **_flatten_and_serialize_metadata(metadata, "observation"),
    }

    return {k: v for k, v in attributes.items() if v is not None}


def _serialize(obj: Any) -> Optional[str]:
    if obj is None or isinstance(obj, str):
        return obj

    return json.dumps(obj, cls=EventSerializer)


def _flatten_and_serialize_metadata(
    metadata: Any, type: Literal["observation", "trace"]
) -> dict:
    prefix = (
        TraceotterOtelSpanAttributes.OBSERVATION_METADATA
        if type == "observation"
        else TraceotterOtelSpanAttributes.TRACE_METADATA
    )

    metadata_attributes: Dict[str, Union[str, int, None]] = {}

    if not isinstance(metadata, dict):
        metadata_attributes[prefix] = _serialize(metadata)
    else:
        for key, value in metadata.items():
            metadata_attributes[f"{prefix}.{key}"] = (
                value
                if isinstance(value, str) or isinstance(value, int)
                else _serialize(value)
            )

    return metadata_attributes
