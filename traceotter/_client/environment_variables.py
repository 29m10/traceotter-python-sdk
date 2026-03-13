"""Environment variable definitions for Traceotter OpenTelemetry integration.

This module defines environment variables used to configure the Traceotter OpenTelemetry integration.
Each environment variable includes documentation on its purpose, expected values, and defaults.
"""

TRACEOTTER_TRACING_ENVIRONMENT = "TRACEOTTER_TRACING_ENVIRONMENT"
"""
.. envvar:: TRACEOTTER_TRACING_ENVIRONMENT

The tracing environment. Can be any lowercase alphanumeric string with hyphens and underscores that does not start with 'traceotter'.

**Default value:** ``"default"``
"""

TRACEOTTER_RELEASE = "TRACEOTTER_RELEASE"
"""
.. envvar:: TRACEOTTER_RELEASE

Release number/hash of the application to provide analytics grouped by release.
"""


TRACEOTTER_PUBLIC_KEY = "TRACEOTTER_PUBLIC_KEY"
"""
.. envvar:: TRACEOTTER_PUBLIC_KEY

Public API key of Traceotter project
"""

TRACEOTTER_SECRET_KEY = "TRACEOTTER_SECRET_KEY"
"""
.. envvar:: TRACEOTTER_SECRET_KEY

Secret API key of Traceotter project
"""

TRACEOTTER_HOST = "TRACEOTTER_HOST"
"""
.. envvar:: TRACEOTTER_HOST

Host of Traceotter API. Can be set via `TRACEOTTER_HOST` environment variable.

**Default value:** ``"https://cloud.traceotter.com"``
"""

TRACEOTTER_DEBUG = "TRACEOTTER_DEBUG"
"""
.. envvar:: TRACEOTTER_DEBUG

Enables debug mode for more verbose logging.

**Default value:** ``"False"``
"""

TRACEOTTER_TRACING_ENABLED = "TRACEOTTER_TRACING_ENABLED"
"""
.. envvar:: TRACEOTTER_TRACING_ENABLED

Enables or disables the Traceotter client. If disabled, all observability calls to the backend will be no-ops. Default is True. Set to `False` to disable tracing.

**Default value:** ``"True"``
"""

TRACEOTTER_MEDIA_UPLOAD_THREAD_COUNT = "TRACEOTTER_MEDIA_UPLOAD_THREAD_COUNT"
"""
.. envvar:: TRACEOTTER_MEDIA_UPLOAD_THREAD_COUNT 

Number of background threads to handle media uploads from trace ingestion.

**Default value:** ``1``
"""

TRACEOTTER_FLUSH_AT = "TRACEOTTER_FLUSH_AT"
"""
.. envvar:: TRACEOTTER_FLUSH_AT

Max batch size until a new ingestion batch is sent to the API.
**Default value:** same as OTEL ``OTEL_BSP_MAX_EXPORT_BATCH_SIZE``
"""

TRACEOTTER_FLUSH_INTERVAL = "TRACEOTTER_FLUSH_INTERVAL"
"""
.. envvar:: TRACEOTTER_FLUSH_INTERVAL

Max delay in seconds until a new ingestion batch is sent to the API.
**Default value:** same as OTEL ``OTEL_BSP_SCHEDULE_DELAY``
"""

TRACEOTTER_SAMPLE_RATE = "TRACEOTTER_SAMPLE_RATE"
"""
.. envvar: TRACEOTTER_SAMPLE_RATE

Float between 0 and 1 indicating the sample rate of traces to bet sent to Traceotter servers.

**Default value**: ``1.0``

"""
TRACEOTTER_OBSERVE_DECORATOR_IO_CAPTURE_ENABLED = (
    "TRACEOTTER_OBSERVE_DECORATOR_IO_CAPTURE_ENABLED"
)
"""
.. envvar: TRACEOTTER_OBSERVE_DECORATOR_IO_CAPTURE_ENABLED

Default capture of function args, kwargs and return value when using the @observe decorator.

Having default IO capture enabled for observe decorated function may have a performance impact on your application
if large or deeply nested objects are attempted to be serialized. Set this value to `False` and use manual
input/output setting on your observation to avoid this.

**Default value**: ``True``
"""

TRACEOTTER_MEDIA_UPLOAD_ENABLED = "TRACEOTTER_MEDIA_UPLOAD_ENABLED"
"""
.. envvar: TRACEOTTER_MEDIA_UPLOAD_ENABLED

Controls whether media detection and upload is attempted by the SDK.

**Default value**: ``True``
"""

TRACEOTTER_TIMEOUT = "TRACEOTTER_TIMEOUT"
"""
.. envvar: TRACEOTTER_TIMEOUT

Controls the timeout for all API requests in seconds

**Default value**: ``5``
"""

TRACEOTTER_PROMPT_CACHE_DEFAULT_TTL_SECONDS = "TRACEOTTER_PROMPT_CACHE_DEFAULT_TTL_SECONDS"
"""
.. envvar: TRACEOTTER_PROMPT_CACHE_DEFAULT_TTL_SECONDS

Controls the default time-to-live (TTL) in seconds for cached prompts.
This setting determines how long prompt responses are cached before they expire.

**Default value**: ``60``
"""
