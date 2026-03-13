""".. include:: ../README.md"""

from traceotter.experiment import Evaluation

from ._client import client as _client_module
from ._client.attributes import TraceotterOtelSpanAttributes
from ._client.constants import ObservationTypeLiteral
from ._client.get_client import get_client
from ._client.observe import observe
from ._client.span import (
    TraceotterAgent,
    TraceotterChain,
    TraceotterEmbedding,
    TraceotterEvaluator,
    TraceotterEvent,
    TraceotterGeneration,
    TraceotterGuardrail,
    TraceotterRetriever,
    TraceotterSpan,
    TraceotterTool,
)

Traceotter = _client_module.Traceotter

__all__ = [
    "Traceotter",
    "get_client",
    "observe",
    "ObservationTypeLiteral",
    "TraceotterSpan",
    "TraceotterGeneration",
    "TraceotterEvent",
    "TraceotterOtelSpanAttributes",
    "TraceotterAgent",
    "TraceotterTool",
    "TraceotterChain",
    "TraceotterEmbedding",
    "TraceotterEvaluator",
    "TraceotterRetriever",
    "TraceotterGuardrail",
    "Evaluation",
    "experiment",
    "api",
]
