from __future__ import annotations

import os
from typing import Iterable


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    # Delayed import so environments without the package can still use other endpoints
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:  # pragma: no cover - import error path
        raise RuntimeError("openai package not installed. Run: pip install -r requirements.txt") from e
    return OpenAI(api_key=api_key)


def stream_chat_chunks(client, **kwargs) -> Iterable[str]:
    # Proxy generator to isolate SDK differences
    stream = client.chat.completions.create(stream=True, **kwargs)
    for chunk in stream:
        delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
        if delta:
            yield delta

