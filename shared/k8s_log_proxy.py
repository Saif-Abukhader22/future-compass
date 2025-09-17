"""
k8s_log_proxy.py

Reusable FastAPI log_router that streams pod logs and lists pods in a namespace,
using the official Kubernetes Python client (no kubectl binary needed).

Features:
- Active only in 'local' or 'development' environments.
- Authenticated via SERVICES_API_KEY_NAME / SERVICES_API_KEY.
- Streams logs with optional `pattern`, `since`, and `tail` parameters.
- Includes a Rich‐based CLI helper for terminal viewing.
- Provides `/pods` endpoint to list pod names.
- Uses Server-Sent Events for browser/React-friendly log streaming.
- Adds `timestamps` via the API.
"""

import argparse
import asyncio
import os
import re
import threading
from queue import Queue
from typing import AsyncIterator, Optional

import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from rich.console import Console
from sse_starlette.sse import EventSourceResponse

from shared.config import shared_settings

# --------------------------------------------------------------------------- #
#  Helper: Detect current namespace from file (standard for K8s pods)
# --------------------------------------------------------------------------- #
def get_current_namespace() -> str:
    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace") as f:
            return f.read().strip()
    except Exception:
        # Fallback for local dev: use 'default'
        return "default"

K8S_NAMESPACE = get_current_namespace()

# --------------------------------------------------------------------------- #
#  Load kube-config (in-cluster or local)
# --------------------------------------------------------------------------- #
try:
    if os.getenv("KUBERNETES_PORT"):
        config.load_incluster_config()
    else:
        config.load_kube_config()
    k8s_core = client.CoreV1Api()
except Exception as e:
    # If the user never imported this in prod, swallow errors.
    k8s_core = None  # type: ignore

# --------------------------------------------------------------------------- #
#  Only register log_router in local/development
# --------------------------------------------------------------------------- #
if shared_settings.ENVIRONMENT not in ("local", "development") or k8s_core is None:
    log_router: APIRouter | None = None
else:
    log_router = APIRouter(tags=["k8s-logs"])

# --------------------------------------------------------------------------- #
#  API key authentication: allow as header or query param for easy browser use
# --------------------------------------------------------------------------- #
def _verify_internal_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias=shared_settings.SERVICES_API_KEY_NAME)
) -> None:
    # Allow API key as header or ?api_key=... in query (for browser devs)
    api_key = x_api_key or request.query_params.get("api_key")
    if api_key != shared_settings.SERVICES_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# --------------------------------------------------------------------------- #
#  CLI helper: stream logs to your terminal with Rich
# --------------------------------------------------------------------------- #
console = Console()
BOLD = "[bold green]"
RESET = "[/bold green]"

def stream_to_terminal() -> None:
    """
    Run as:
        python -m k8s_log_proxy http://localhost:8000/internal/logs/my-pod \
            --api-key <SERVICES_API_KEY> --pattern ERROR --since 300 --tail 200
    Note: `since` is seconds here, not "5m". You can convert.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Full logs endpoint URL")
    parser.add_argument("--api-key", required=True, help="Internal API key")
    parser.add_argument("--pattern", help="Regex to filter log lines")
    parser.add_argument("--since", type=int, help="Only logs newer than this (seconds)")
    parser.add_argument("--tail", type=int, help="Last N lines initially")
    args = parser.parse_args()

    headers = {shared_settings.SERVICES_API_KEY_NAME: args.api_key}
    params = {}
    for p in ("pattern", "since", "tail"):
        val = getattr(args, p)
        if val is not None:
            params[p] = str(val)

    with requests.get(args.url, headers=headers, params=params, stream=True) as resp:
        resp.raise_for_status()
        for raw in resp.iter_lines():
            if raw.startswith(b"data:"):
                console.print(f"{BOLD}{raw[5:].decode()}{RESET}")

if __name__ == "__main__" and shared_settings.ENVIRONMENT in ("local", "development"):
    stream_to_terminal()

# --------------------------------------------------------------------------- #
#  Helper: Async log generator via Kubernetes API
# --------------------------------------------------------------------------- #
async def _log_generator(
    pod: str,
    container: Optional[str],
    pattern: Optional[str],
    since_seconds: Optional[int],
    tail_lines: Optional[int],
) -> AsyncIterator[str]:
    w = watch.Watch()
    regex = re.compile(pattern) if pattern else None
    q: Queue = Queue(maxsize=100)

    def sync_stream():
        try:
            stream = w.stream(
                k8s_core.read_namespaced_pod_log,
                name=pod,
                namespace=K8S_NAMESPACE,
                container=container,
                follow=True,
                timestamps=True,
                since_seconds=since_seconds,
                tail_lines=tail_lines,
                _preload_content=False,
            )
            for chunk in stream:
                if not regex or regex.search(chunk):
                    q.put(chunk)
        except Exception as e:
            q.put(None)  # Signal finish on error or complete
        finally:
            q.put(None)

    thread = threading.Thread(target=sync_stream, daemon=True)
    thread.start()

    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, q.get)
        except Exception:
            break
        if line is None:
            break
        yield line

# --------------------------------------------------------------------------- #
#  FastAPI endpoints
# --------------------------------------------------------------------------- #
if log_router:

    @log_router.get(
        "/logs/{pod}",
        summary="Stream pod logs (SSE)",
        dependencies=[Depends(_verify_internal_api_key)],
        response_class=EventSourceResponse
    )
    async def stream_logs_sse(
        request: Request,
        pod: str,
        container: Optional[str] = None,
        pattern: Optional[str] = None,
        since: Optional[int] = None,  # seconds
        tail: Optional[int] = None,   # last N lines
    ):
        """
        Streams logs as Server-Sent Events.

        Query params:
        - api_key: API key (can be provided for browser testing)
        - container: specify container if pod has multiple
        - pattern:   regex filter (ERROR, WARN, etc.)
        - since:     only logs newer than this (seconds)
        - tail:      number of last lines to fetch initially
        """
        gen = _log_generator(pod, container, pattern, since, tail)
        return EventSourceResponse(({"data": ln} async for ln in gen))

    @log_router.get(
        "/pods",
        summary="List pod names in namespace",
        dependencies=[Depends(_verify_internal_api_key)],
    )
    async def list_pods():
        """
        Returns JSON:
          { "pods": ["pod-1", "pod-2", ...] }
        """
        try:
            resp = k8s_core.list_namespaced_pod(namespace=K8S_NAMESPACE)
        except ApiException as e:
            raise HTTPException(status_code=e.status, detail=e.reason)
        names = [p.metadata.name for p in resp.items]
        return {"pods": names}
