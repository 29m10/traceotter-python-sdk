"""@private"""

import json
import logging
from base64 import b64encode
from typing import Any, Dict, List, Union

import httpx

from traceotter._utils.serializer import EventSerializer
from traceotter._utils.ingest_schema import RawSpan


def _build_ingest_payload(spans: List[RawSpan]) -> List[Dict[str, Any]]:
    """
    Construct the HTTP payload expected by the /v1/ingest API from a list of RawSpan objects.

    The API expects a top-level JSON array of envelopes, each containing a ``spans`` array
    where each span has:
      - ``details`` (required): the RawSpan payload
      - ``name`` (optional): logical span name

    We currently group all RawSpans from a batch into a single envelope.
    """
    if not spans:
        return []

    envelope: Dict[str, Any] = {"spans": []}
    for span in spans:
        if not isinstance(span, dict):
            # Defensive: skip non-dict entries; they would fail validation server-side anyway.
            continue

        span_wrapper: Dict[str, Any] = {"details": span}

        # If a logical name is already present on the RawSpan, surface it at the wrapper level
        # so the backend can copy it into details["name"] when missing.
        name = span.get("name")
        if isinstance(name, str) and name:
            span_wrapper["name"] = name

        envelope["spans"].append(span_wrapper)

    if not envelope["spans"]:
        return []

    return [envelope]


class TraceotterClient:
    _public_key: str
    _secret_key: str
    _base_url: str
    _version: str
    _timeout: int
    _session: httpx.Client

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        base_url: str,
        version: str,
        timeout: int,
        session: httpx.Client,
    ):
        self._public_key = public_key
        self._secret_key = secret_key
        self._base_url = base_url
        self._version = version
        self._timeout = timeout
        self._session = session

    def generate_headers(self) -> dict:
        return {
            "Authorization": "Basic "
            + b64encode(
                f"{self._public_key}:{self._secret_key}".encode("utf-8")
            ).decode("ascii"),
            "Content-Type": "application/json",
            "x_traceotter_sdk_name": "python",
            "x_traceotter_sdk_version": self._version,
            "x_traceotter_public_key": self._public_key,
        }

    def batch_post(self, spans: List[RawSpan]) -> httpx.Response:
        """Post a batch of RawSpan objects to the v1/ingest API endpoint."""
        log = logging.getLogger("traceotter")
        log.debug("uploading spans: %s", spans)

        # Convert RawSpans into the HTTP payload shape expected by /v1/ingest.
        payload = _build_ingest_payload(spans)

        res = self.post(payload)
        return self._process_response(
            res, success_message="data uploaded successfully", return_json=False
        )

    def post(self, payload: List[Dict[str, Any]]) -> httpx.Response:
        """
        Post the provided envelopes list to the v1/ingest API.

        The payload must match the documented schema:
        [
            {
                "spans": [
                    {
                        "details": { ... RawSpan ... },
                        "name": "optional-logical-name"
                    },
                    ...
                ]
            }
        ]
        """
        log = logging.getLogger("traceotter")
        url = self._remove_trailing_slash(self._base_url) + "/v1/ingest"
        data = json.dumps(payload, cls=EventSerializer)
        log.debug("making request to %s with %d envelopes", url, len(payload))
        headers = self.generate_headers()
        res = self._session.post(
            url, content=data, headers=headers, timeout=self._timeout
        )

        if res.status_code == 200:
            log.debug("data uploaded successfully")

        return res

    def _remove_trailing_slash(self, url: str) -> str:
        """Removes the trailing slash from a URL"""
        if url.endswith("/"):
            return url[:-1]
        return url

    def _process_response(
        self, res: httpx.Response, success_message: str, *, return_json: bool = True
    ) -> Union[httpx.Response, Any]:
        log = logging.getLogger("traceotter")
        log.debug("received response: %s", res.text)
        if res.status_code in (200, 201):
            log.debug(success_message)
            if return_json:
                try:
                    return res.json()
                except json.JSONDecodeError:
                    raise APIError(res.status_code, "Invalid JSON response received")
            else:
                return res
        elif res.status_code == 207:
            try:
                payload = res.json()
                errors = payload.get("errors", [])
                if errors:
                    raise APIErrors(
                        [
                            APIError(
                                error.get("status"),
                                error.get("message", "No message provided"),
                                error.get("error", "No error details provided"),
                            )
                            for error in errors
                        ]
                    )
                else:
                    return res.json() if return_json else res
            except json.JSONDecodeError:
                raise APIError(res.status_code, "Invalid JSON response received")

        try:
            payload = res.json()
            raise APIError(res.status_code, payload)
        except (KeyError, ValueError):
            raise APIError(res.status_code, res.text)


class APIError(Exception):
    def __init__(self, status: Union[int, str], message: str, details: Any = None):
        self.message = message
        self.status = status
        self.details = details

    def __str__(self) -> str:
        msg = "{0} ({1}): {2}"
        return msg.format(self.message, self.status, self.details)


class APIErrors(Exception):
    def __init__(self, errors: List[APIError]):
        self.errors = errors

    def __str__(self) -> str:
        errors = ", ".join(str(error) for error in self.errors)

        return f"[Traceotter] {errors}"
