import json
import logging
import os
import threading
import time
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

import backoff

from ..version import __version__ as traceotter_version

try:
    import pydantic.v1 as pydantic
except ImportError:
    import pydantic  # type: ignore

from traceotter._utils.parse_error import handle_exception
from traceotter._utils.request import APIError, TraceotterClient
from traceotter._utils.serializer import EventSerializer
from traceotter._utils.ingest_schema import (
    ErrorCode,
    RawSpan,
    SchemaValidationError,
)

MAX_EVENT_SIZE_BYTES = int(os.environ.get("TRACEOTTER_MAX_EVENT_SIZE_BYTES", 1_000_000))
MAX_BATCH_SIZE_BYTES = int(os.environ.get("TRACEOTTER_MAX_BATCH_SIZE_BYTES", 2_500_000))


class ScoreIngestionMetadata(pydantic.BaseModel):
    batch_size: int
    sdk_name: str
    sdk_version: str
    public_key: str


class ScoreIngestionConsumer(threading.Thread):
    _log = logging.getLogger("traceotter")

    def __init__(
        self,
        *,
        ingestion_queue: Queue,
        identifier: int,
        client: TraceotterClient,
        public_key: str,
        flush_at: Optional[int] = None,
        flush_interval: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        """Create a consumer thread."""
        super().__init__()
        # It's important to set running in the constructor: if we are asked to
        # pause immediately after construction, we might set running to True in
        # run() *after* we set it to False in pause... and keep running
        # forever.
        self.running = True
        # Make consumer a daemon thread so that it doesn't block program exit
        self.daemon = True
        self._ingestion_queue = ingestion_queue
        self._identifier = identifier
        self._client = client
        self._flush_at = flush_at or 15
        self._flush_interval = flush_interval or 1
        self._max_retries = max_retries or 3
        self._public_key = public_key

    def _next(self) -> list:
        """Return the next batch of items to upload."""
        events: list = []

        start_time = time.monotonic()
        total_size = 0

        while len(events) < self._flush_at:
            elapsed = time.monotonic() - start_time
            if elapsed >= self._flush_interval:
                break
            try:
                event = self._ingestion_queue.get(
                    block=True, timeout=self._flush_interval - elapsed
                )

                # convert pydantic models to dicts
                if "body" in event and isinstance(event["body"], pydantic.BaseModel):
                    event["body"] = event["body"].dict(exclude_none=True)

                item_size = self._get_item_size(event)

                # check for serialization errors
                try:
                    json.dumps(event, cls=EventSerializer)
                except Exception as e:
                    self._log.error(
                        f"Data error: Failed to serialize score object for ingestion. Score will be dropped. Error: {e}"
                    )
                    self._ingestion_queue.task_done()

                    continue

                events.append(event)

                total_size += item_size
                if total_size >= MAX_BATCH_SIZE_BYTES:
                    self._log.debug(
                        f"Batch management: Reached maximum batch size limit ({total_size} bytes). Processing {len(events)} events now."
                    )
                    break

            except Empty:
                break

            except Exception as e:
                self._log.warning(
                    f"Data processing error: Failed to process score event in consumer thread #{self._identifier}. Event will be dropped. Error: {str(e)}",
                    exc_info=True,
                )
                self._ingestion_queue.task_done()

        return events

    def _get_item_size(self, item: Any) -> int:
        """Return the size of the item in bytes."""
        return len(json.dumps(item, cls=EventSerializer).encode())

    def run(self) -> None:
        """Run the consumer."""
        self._log.debug(
            f"Startup: Score ingestion consumer thread #{self._identifier} started with batch size {self._flush_at} and interval {self._flush_interval}s"
        )
        while self.running:
            self.upload()

    def upload(self) -> None:
        """Upload the next batch of items, return whether successful."""
        batch = self._next()
        if len(batch) == 0:
            return

        try:
            self._upload_batch(batch)
        except Exception as e:
            handle_exception(e)
        finally:
            # mark items as acknowledged from queue
            for _ in batch:
                self._ingestion_queue.task_done()

    def pause(self) -> None:
        """Pause the consumer."""
        self.running = False

    def _upload_batch(self, batch: List[Any]) -> None:
        self._log.debug(
            f"API: Uploading batch of {len(batch)} score events to Traceotter API"
        )

        metadata = ScoreIngestionMetadata(
            batch_size=len(batch),
            sdk_name="python",
            sdk_version=traceotter_version,
            public_key=self._public_key,
        ).dict()

        spans: List[RawSpan] = []
        for event in batch:
            try:
                span = self._event_to_span(event, metadata)
                spans.append(span)
            except SchemaValidationError as e:
                self._log.error(
                    f"Schema validation error: Dropping score event for ingestion. Error: {e}"
                )
            except Exception as e:
                self._log.error(
                    f"Data processing error: Failed to convert score event to span. Event will be dropped. Error: {e}"
                )

        if not spans:
            # Nothing valid to send
            return

        @backoff.on_exception(
            backoff.expo, Exception, max_tries=self._max_retries, logger=None
        )
        def execute_task_with_backoff(spans: List[RawSpan]) -> None:
            try:
                self._client.batch_post(spans)
            except Exception as e:
                if (
                    isinstance(e, APIError)
                    and 400 <= int(e.status) < 500
                    and int(e.status) != 429  # retry if rate-limited
                ):
                    return

                raise e

        execute_task_with_backoff(spans)
        self._log.debug(
            f"API: Successfully sent {len(batch)} score events to Traceotter API in batch mode"
        )

    def _event_to_span(self, event: Dict[str, Any], metadata: Dict[str, Any]) -> RawSpan:
        """
        Convert a score ingestion event into a RawSpan suitable for /v1/ingest.

        The resulting span:
        - Uses the event id as span_id
        - Uses the event timestamp as start_time
        - Derives trace_id from the score body
        - Packs score-specific details and ingestion metadata into attributes
        """
        body = event.get("body") or {}

        # Body may still be a Pydantic model if it bypassed _next conversion
        try:
            import pydantic.v1 as pydantic_v1  # type: ignore
        except ImportError:  # pragma: no cover - fallback if v1 not installed
            import pydantic as pydantic_v1  # type: ignore

        if hasattr(pydantic_v1, "BaseModel") and isinstance(
            body, pydantic_v1.BaseModel  # type: ignore[arg-type]
        ):
            body = body.dict(exclude_none=True, by_alias=True)

        if not isinstance(body, dict):
            raise SchemaValidationError(
                ErrorCode.INVALID_SPAN,
                f"Expected score event body to be a dict, got {type(body).__name__}",
            )

        # Derive identifiers
        trace_id = body.get("traceId") or body.get("trace_id")
        span_id = event.get("id") or body.get("id")

        # Build attributes payload
        attributes: Dict[str, Any] = {}

        # Include score core fields
        for key in (
            "name",
            "environment",
            "queueId",
            "comment",
            "metadata",
            "dataType",
            "configId",
            "sessionId",
            "observationId",
            "datasetRunId",
        ):
            if key in body and body[key] is not None:
                attributes[key] = body[key]

        # Attach trace-related identifiers into attributes as well
        if trace_id is not None:
            attributes.setdefault("trace_id", trace_id)

        # Attach ingestion metadata under a namespaced key
        attributes["_ingest"] = {
            "batch_size": metadata.get("batch_size"),
            "sdk_name": metadata.get("sdk_name"),
            "sdk_version": metadata.get("sdk_version"),
            "public_key": metadata.get("public_key"),
            "type": event.get("type"),
        }

        span: RawSpan = {
            # Allow validator to resolve span_id from either 'span_id' or 'id'
            "id": span_id,
            "trace_id": trace_id,
            "start_time": event.get("timestamp"),
            "attributes": attributes,
        }

        # Validate and normalize according to v1/ingest schema
        from traceotter._utils.ingest_schema import validate_span_schema

        return validate_span_schema(span)

