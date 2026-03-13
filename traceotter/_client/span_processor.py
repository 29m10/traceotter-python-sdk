"""Span processor for Traceotter OpenTelemetry integration.

This module defines the TraceotterSpanProcessor class, which extends OpenTelemetry's
BatchSpanProcessor with Traceotter-specific functionality. It handles exporting
spans to the Traceotter API with proper authentication and filtering.

Key features:
- HTTP-based span export to Traceotter API
- Basic authentication with Traceotter API keys
- Configurable batch processing behavior
- Project-scoped span filtering to prevent cross-project data leakage
"""

import base64
import os
from typing import Dict, List, Optional, Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExportResult,
    SpanExporter,
)

from traceotter._client.constants import TRACEOTTER_TRACER_NAME
from traceotter._client.environment_variables import (
    TRACEOTTER_FLUSH_AT,
    TRACEOTTER_FLUSH_INTERVAL,
)
from traceotter._client.utils import span_formatter
from traceotter.logger import traceotter_logger
from traceotter.version import __version__ as traceotter_version
from traceotter._utils.ingest_schema import RawSpan, SchemaValidationError, validate_span_schema
from traceotter._utils.request import TraceotterClient


class TraceotterIngestSpanExporter(SpanExporter):
    """Custom span exporter that sends spans to /v1/ingest as RawSpan objects."""

    def __init__(
        self,
        *,
        public_key: str,
        secret_key: str,
        host: str,
        timeout: Optional[int],
    ):
        basic_auth_header = "Basic " + base64.b64encode(
            f"{public_key}:{secret_key}".encode("utf-8")
        ).decode("ascii")

        # Minimal httpx client is created inside TraceotterClient by the resource manager.
        # Here we only configure credentials and timeout.
        import httpx

        session = httpx.Client(timeout=timeout)
        self._client = TraceotterClient(
            public_key=public_key,
            secret_key=secret_key,
            base_url=host,
            version=traceotter_version,
            timeout=timeout or 20,
            session=session,
        )

    def export(self, spans: Sequence[ReadableSpan]) -> "SpanExportResult":
        raw_spans: List[RawSpan] = []

        for span in spans:
            try:
                raw = self._span_to_raw_span(span)
                raw = validate_span_schema(raw)
                raw_spans.append(raw)
            except SchemaValidationError as e:
                traceotter_logger.error(
                    f"Schema validation error while exporting span. Span will be dropped. Error: {e}"
                )
            except Exception as e:
                traceotter_logger.error(
                    f"Unexpected error while converting span to RawSpan. Span will be dropped. Error: {e}"
                )

        if not raw_spans:
            return SpanExportResult.SUCCESS

        try:
            self._client.batch_post(raw_spans)
            return SpanExportResult.SUCCESS
        except Exception as e:
            traceotter_logger.error(
                f"Failed to export {len(raw_spans)} spans to /v1/ingest. Error: {e}"
            )
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        # Nothing special to do; HTTPX client is managed by TraceotterClient
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        # All exports are synchronous; nothing buffered here.
        return True

    @staticmethod
    def _span_to_raw_span(span: ReadableSpan) -> RawSpan:
        """Convert an OpenTelemetry ReadableSpan into a RawSpan."""
        # IDs: represent as lowercase hex
        ctx = span.context
        trace_id = "{:032x}".format(ctx.trace_id) if ctx and ctx.trace_id is not None else None
        span_id = "{:016x}".format(ctx.span_id) if ctx and ctx.span_id is not None else None

        # Parent span id (if any)
        parent_ctx = span.parent
        parent_span_id = (
            "{:016x}".format(parent_ctx.span_id)
            if parent_ctx is not None and parent_ctx.span_id is not None
            else None
        )

        # Start time: OpenTelemetry stores time as nanoseconds since epoch
        start_time = span.start_time / 1e9 if span.start_time is not None else None

        attributes: Dict[str, object] = {}
        if span.attributes:
            attributes.update(span.attributes)

        # Also surface OTEL name and status in attributes for debugging
        attributes.setdefault("otel_span_name", getattr(span, "_name", None))
        if span.status is not None:
            attributes.setdefault("otel_status_code", getattr(span.status, "status_code", None))
            attributes.setdefault("otel_status_description", getattr(span.status, "description", None))

        # Capture parent-child relationships explicitly so the backend can reconstruct the tree
        if parent_span_id is not None:
            attributes.setdefault("parent_span_id", parent_span_id)

        # Also provide a context object mirroring how identifiers can be read by the ingest schema
        context: Dict[str, object] = {}
        if trace_id is not None:
            context["trace_id"] = trace_id
        if span_id is not None:
            context["span_id"] = span_id
        if parent_span_id is not None:
            context["parent_span_id"] = parent_span_id

        raw_span: RawSpan = {
            "trace_id": trace_id,
            "id": span_id,
            "start_time": start_time,
            "attributes": attributes,
        }

        if context:
            raw_span["context"] = context

        return raw_span


class TraceotterSpanProcessor(BatchSpanProcessor):
    """OpenTelemetry span processor that exports spans to the Traceotter API.

    This processor extends OpenTelemetry's BatchSpanProcessor with Traceotter-specific functionality:
    1. Project-scoped span filtering to prevent cross-project data leakage
    2. Instrumentation scope filtering to block spans from specific libraries/frameworks
    3. Configurable batch processing parameters for optimal performance
    4. HTTP-based span export to the Traceotter OTLP endpoint
    5. Debug logging for span processing operations
    6. Authentication with Traceotter API using Basic Auth

    The processor is designed to efficiently handle large volumes of spans with
    minimal overhead, while ensuring spans are only sent to the correct project.
    It integrates with OpenTelemetry's standard span lifecycle, adding Traceotter-specific
    filtering and export capabilities.
    """

    def __init__(
        self,
        *,
        public_key: str,
        secret_key: str,
        host: str,
        timeout: Optional[int] = None,
        flush_at: Optional[int] = None,
        flush_interval: Optional[float] = None,
        blocked_instrumentation_scopes: Optional[List[str]] = None,
        additional_headers: Optional[Dict[str, str]] = None,
    ):
        self.public_key = public_key
        self.blocked_instrumentation_scopes = (
            blocked_instrumentation_scopes
            if blocked_instrumentation_scopes is not None
            else []
        )

        env_flush_at = os.environ.get(TRACEOTTER_FLUSH_AT, None)
        flush_at = flush_at or int(env_flush_at) if env_flush_at is not None else None

        env_flush_interval = os.environ.get(TRACEOTTER_FLUSH_INTERVAL, None)
        flush_interval = (
            flush_interval or float(env_flush_interval)
            if env_flush_interval is not None
            else None
        )

        # Additional headers are no longer needed at the OTLP level since we now
        # send spans directly to /v1/ingest via TraceotterClient.
        _ = additional_headers

        super().__init__(
            span_exporter=TraceotterIngestSpanExporter(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
                timeout=timeout,
            ),
            export_timeout_millis=timeout * 1_000 if timeout else None,
            max_export_batch_size=flush_at,
            schedule_delay_millis=flush_interval * 1_000
            if flush_interval is not None
            else None,
        )

    def on_end(self, span: ReadableSpan) -> None:
        # Only export spans that belong to the scoped project
        # This is important to not send spans to wrong project in multi-project setups
        if self._is_traceotter_span(span) and not self._is_traceotter_project_span(span):
            traceotter_logger.debug(
                f"Security: Span rejected - belongs to project '{span.instrumentation_scope.attributes.get('public_key') if span.instrumentation_scope and span.instrumentation_scope.attributes else None}' but processor is for '{self.public_key}'. "
                f"This prevents cross-project data leakage in multi-project environments."
            )
            return

        # Do not export spans from blocked instrumentation scopes
        if self._is_blocked_instrumentation_scope(span):
            return

        traceotter_logger.debug(
            f"Trace: Processing span name='{span._name}' | Full details:\n{span_formatter(span)}"
        )

        super().on_end(span)

    @staticmethod
    def _is_traceotter_span(span: ReadableSpan) -> bool:
        return (
            span.instrumentation_scope is not None
            and span.instrumentation_scope.name == TRACEOTTER_TRACER_NAME
        )

    def _is_blocked_instrumentation_scope(self, span: ReadableSpan) -> bool:
        return (
            span.instrumentation_scope is not None
            and span.instrumentation_scope.name in self.blocked_instrumentation_scopes
        )

    def _is_traceotter_project_span(self, span: ReadableSpan) -> bool:
        if not TraceotterSpanProcessor._is_traceotter_span(span):
            return False

        if span.instrumentation_scope is not None:
            public_key_on_span = (
                span.instrumentation_scope.attributes.get("public_key", None)
                if span.instrumentation_scope.attributes
                else None
            )

            return public_key_on_span == self.public_key

        return False
