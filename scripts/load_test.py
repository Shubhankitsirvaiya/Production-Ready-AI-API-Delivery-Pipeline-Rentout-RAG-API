"""Small asynchronous load generator for Project 12 reliability demonstrations.

The safe default targets GET /health, which does not call OpenAI. To exercise the
full RAG path intentionally, pass --endpoint /chat and choose a conservative
request count because every successful chat can consume paid API tokens.
"""

# Keep annotation evaluation compatible across supported Python versions.
from __future__ import annotations

# argparse turns command-line flags into typed settings.
import argparse

# asyncio runs many HTTP requests concurrently on one event loop.
import asyncio

# time.perf_counter provides precise duration measurements.
import time

# Any supports the optional JSON response body shape.
from typing import Any

# httpx.AsyncClient performs non-blocking HTTP requests.
import httpx


def parse_args() -> argparse.Namespace:
    """Read and validate load-test command-line settings."""

    # Describe the tool in `python scripts/load_test.py --help`.
    parser = argparse.ArgumentParser(description="Async load test for the RentOut Kubernetes API")

    # Base URL normally points to the port-forward opened by open-dashboards.ps1.
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")

    # Health is safe and free; /chat intentionally exercises the complete RAG path.
    parser.add_argument("--endpoint", choices=["/health", "/ops/status", "/chat"], default="/health")

    # Total number of requests sent during one test run.
    parser.add_argument("--requests", type=int, default=100)

    # Maximum simultaneous requests; this demonstrates async concurrency.
    parser.add_argument("--concurrency", type=int, default=10)

    # Bound individual request duration so failures do not hang the run forever.
    parser.add_argument("--timeout", type=float, default=120.0)

    # Question is used only when the selected endpoint is /chat.
    parser.add_argument("--question", default="What happens if furniture is damaged during my rental?")

    # Parse the actual shell arguments.
    args = parser.parse_args()

    # Refuse nonsensical values with a clear message.
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must both be positive")

    return args


def percentile(values: list[float], percent: float) -> float:
    """Return a nearest-rank latency percentile from millisecond values."""

    # Empty results occur only when every task failed before recording latency.
    if not values:
        return 0.0

    # Sort a copy so percentile lookup does not mutate caller-owned results.
    ordered = sorted(values)

    # Convert the percentile to a bounded zero-based list index.
    index = min(len(ordered) - 1, max(0, int((percent / 100) * len(ordered))))

    return ordered[index]


async def send_request(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    endpoint: str,
    question: str,
) -> tuple[bool, float, int | None, str | None]:
    """Send one bounded request and return success, latency, status, and error."""

    # The semaphore caps in-flight work at the requested concurrency.
    async with semaphore:
        started = time.perf_counter()

        try:
            # /chat requires JSON; status endpoints are simple GET requests.
            if endpoint == "/chat":
                payload: dict[str, Any] = {"question": question}
                response = await client.post(endpoint, json=payload)
            else:
                response = await client.get(endpoint)

            # Convert seconds to milliseconds for readable reports.
            latency_ms = (time.perf_counter() - started) * 1000

            # Treat every 2xx response as successful.
            success = 200 <= response.status_code < 300

            return success, latency_ms, response.status_code, None

        except Exception as exc:
            # Network failures still contribute to elapsed latency and error counts.
            latency_ms = (time.perf_counter() - started) * 1000
            return False, latency_ms, None, str(exc)


async def run(args: argparse.Namespace) -> None:
    """Execute all requests and print a compact reliability report."""

    # Prevent accidental expensive high-volume chat tests.
    if args.endpoint == "/chat" and args.requests > 50:
        raise ValueError("/chat is capped at 50 requests to limit accidental OpenAI cost")

    # Semaphore is shared by every task and enforces concurrency.
    semaphore = asyncio.Semaphore(args.concurrency)

    # Configure one reusable connection pool for the complete run.
    timeout = httpx.Timeout(args.timeout)
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)

    run_started = time.perf_counter()

    async with httpx.AsyncClient(base_url=args.base_url, timeout=timeout, limits=limits) as client:
        # Create all coroutine objects first; gather schedules them concurrently.
        tasks = [
            send_request(client, semaphore, args.endpoint, args.question)
            for _ in range(args.requests)
        ]

        # Wait for every result so success rate and percentiles use the whole sample.
        results = await asyncio.gather(*tasks)

    total_seconds = time.perf_counter() - run_started

    # Extract aggregate values from the result tuples.
    successes = sum(1 for success, _, _, _ in results if success)
    failures = len(results) - successes
    latencies = [latency for _, latency, _, _ in results]
    throughput = len(results) / total_seconds if total_seconds else 0.0

    print(f"Endpoint:       {args.base_url}{args.endpoint}")
    print(f"Requests:       {len(results)}")
    print(f"Concurrency:    {args.concurrency}")
    print(f"Successes:      {successes}")
    print(f"Failures:       {failures}")
    print(f"Success rate:   {(successes / len(results)) * 100:.2f}%")
    print(f"Throughput:     {throughput:.2f} requests/second")
    print(f"Average latency:{sum(latencies) / len(latencies):.2f} ms")
    print(f"P50 latency:    {percentile(latencies, 50):.2f} ms")
    print(f"P95 latency:    {percentile(latencies, 95):.2f} ms")
    print(f"P99 latency:    {percentile(latencies, 99):.2f} ms")

    # Print a small sample of errors when failures occurred.
    errors = [error for _, _, _, error in results if error]
    for error in errors[:5]:
        print(f"Error sample:   {error}")


# Execute only when run as a script, not when imported by tests.
if __name__ == "__main__":
    # asyncio.run creates and closes the event loop for the load test.
    asyncio.run(run(parse_args()))
