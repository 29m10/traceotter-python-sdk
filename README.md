# Traceotter

An observability and analytics layer for LLM applications and agents.  
Traceotter lets you capture traces, spans, tool calls, generations, and evaluations so you can debug, monitor, and improve AI systems with real production data.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/traceotter.svg)](https://pypi.org/project/traceotter/)

> **Acknowledgement**  
> Traceotter is inspired by the excellent work on LLM observability from [Langfuse](https://langfuse.com/).  
> Many concepts and patterns in this SDK build on ideas they pioneered for the ecosystem.

---

## Features

- **End‑to‑end tracing**: Model entire requests as traces composed of nested spans.
- **Rich span types**: Generations, tools, chains, agents, evaluators, retrievers, and custom events.
- **Low‑friction instrumentation**: Decorators (`@observe`) and helpers that work with your existing code.
- **Typed SDK**: Generated models and clients for a great editor and type‑checking experience.
- **Sync and async support**: Built on `httpx` with configurable timeouts and retries.
- **Production‑ready**: Designed for long‑running services, background workers, and agent frameworks.

---

## Installation

### Basic Installation

```bash
pip install traceotter
```

### Development Installation

```bash
git clone https://github.com/29m10/traceotter-python-sdk.git
cd traceotter-python-sdk
pip install -e .
```

---

## Prerequisites

To send data, you need:

- Python **3.8+**
- A running **Traceotter backend** (local or hosted)
- Project keys for that backend:
  - `TRACEOTTER_PUBLIC_KEY`
  - `TRACEOTTER_SECRET_KEY`

The SDK is just the client; it does not host the backend itself.

---

## Quick Start

### 1. Configure Traceotter

You can configure Traceotter either via **environment variables** or by passing values directly to `get_client`.

#### Option A: Environment Variables (recommended)

```bash
export TRACEOTTER_HOST="https://api.traceotter.com"
export TRACEOTTER_PUBLIC_KEY="your-traceotter-public-key"
export TRACEOTTER_SECRET_KEY="your-traceotter-secret-key"
```

Then in your code:

```python
from traceotter import get_client

client = get_client()
```

#### Option B: Configuration in Code

```python
from traceotter import get_client

client = get_client(
    host="http://127.0.0.1:8000",
    public_key="your-traceotter-public-key",
    secret_key="your-traceotter-secret-key",
)
```

Use whichever option best fits your deployment model; you only need **one**.

---

### 2. Trace a Simple Function

The quickest way to start seeing data in Traceotter is to wrap functions with `@observe`.

```python
from traceotter import observe

@observe(type="generation")
def generate_answer(question: str) -> str:
    # Call your LLM here (OpenAI, Anthropic, local model, etc.)
    return f"Echo: {question}"

if __name__ == "__main__":
    print(generate_answer("What is Traceotter?"))
```

Every call to `generate_answer` is captured as a span in a trace, with inputs and outputs attached.

---

### 3. Example with an LLM Call

Below is a conceptual example; adapt it to whichever LLM provider you use:

```python
from traceotter import observe

@observe(type="generation")
def ask_model(prompt: str) -> str:
    # Replace this with your actual LLM client
    completion = some_llm_client.generate(prompt=prompt)
    return completion.text

response = ask_model("Explain Traceotter in one sentence.")
print(response)
```

You can layer additional spans (tools, chains, evaluators) on top of this pattern as your system grows.

---

## Configuration

### Environment‑based Configuration

If you follow the environment‑variable path, the SDK will look for:

- `TRACEOTTER_HOST` – Base URL of the Traceotter backend  
+- `TRACEOTTER_PUBLIC_KEY` – Public key for your project  
+- `TRACEOTTER_SECRET_KEY` – Secret key for authenticated communication  

Example `.env`:

```bash
TRACEOTTER_HOST="https://api.traceotter.com"
TRACEOTTER_PUBLIC_KEY="pk-..."
TRACEOTTER_SECRET_KEY="sk-..."
```

Load it in your app (e.g. via `python-dotenv` or your framework’s config system) and call:

```python
from traceotter import get_client

client = get_client()
```

### Code‑based Configuration

For scripts, tests, or environments where you don’t want to rely on env vars:

```python
from traceotter import get_client

client = get_client(
    host="https://api.traceotter.com",
    public_key="pk-...",
    secret_key="sk-...",
)
```

---

## Usage Examples

### Adding Observability to an Agent / Service

```python
from traceotter import observe

class SupportAgent:
    @observe(type="agent")
    def handle_request(self, user_id: str, message: str) -> str:
        # Run your business logic / LLM calls / tools here
        reply = self._route_and_generate(user_id, message)
        return reply

    @observe(type="tool")
    def _lookup_user_profile(self, user_id: str) -> dict:
        # Example tool span
        return {"user_id": user_id, "segment": "beta"}

agent = SupportAgent()
response = agent.handle_request("user-123", "Can you reset my password?")
```

Each decorated method produces structured spans, keeping the trace graph aligned with your code structure.

### Manual Span Usage (Conceptual)

If you need more control than decorators provide, you can work with lower‑level APIs (e.g. to create spans programmatically, attach metadata, or integrate deeply with frameworks). The SDK exposes types like:

- `TraceotterSpan`
- `TraceotterGeneration`
- `TraceotterTool`
- `TraceotterAgent`
- `TraceotterChain`
- `TraceotterEvaluator`
- `TraceotterRetriever`

You can gradually move from simple decorator‑based instrumentation to more advanced patterns as the system evolves.

---

## Architecture (High‑Level)

At a high level, the Traceotter SDK:

1. Captures events from your application (via decorators or explicit calls).
2. Builds traces with nested spans representing your logical call graph.
3. Serializes and sends them to the Traceotter backend using `httpx`.
4. Relies on the backend to store, index, and expose this data for querying, dashboards, and analysis.

The client is stateless and can be safely used in web servers, background workers, and long‑running processes.

---

## Development

### Local Development Setup

```bash
git clone https://github.com/29m10/traceotter-python-sdk.git
cd traceotter-python-sdk
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Tests and Quality

```bash
# Run tests (if test suite is configured)
pytest

# Example lint/format commands (adjust to your actual tooling)
ruff check .
ruff format .
mypy traceotter
```

Generated or API‑client code may be overwritten by future generation runs. If you want to modify
those parts, open an issue first so we can coordinate changes at the generation layer.

---

## Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-improvement`.
3. Make your changes and add tests where appropriate.
4. Run the test suite and linters.
5. Open a Pull Request describing the motivation and approach.

Bug reports and feature requests are also appreciated via GitHub Issues.

---

## License

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.

---

## Links

- Repository: <https://github.com/29m10/traceotter-python-sdk>
- Issues: <https://github.com/29m10/traceotter-python-sdk/issues>
- PyPI: <https://pypi.org/project/traceotter/>

---

## Acknowledgements

- **Langfuse** – for pioneering many of the observability concepts and patterns that inspired Traceotter.
- The broader LLM tooling community pushing standards around tracing, evaluation, and production readiness.

