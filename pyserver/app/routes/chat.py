from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..db import db
from ..services.openai_client import get_openai_client, stream_chat_chunks

# Extra system guidance so the assistant can render degree/self-study plans
PLAN_INSTRUCTIONS = (
    "When the user asks for a degree plan, major roadmap, prerequisite tree, curriculum flow, or a self-study roadmap, respond with a short intro (1-2 lines) and then include a single fenced code block using language tag 'degreeplan' that contains STRICT JSON matching this TypeScript shape: \n"
    "{ level: 'bachelor' | 'master' | 'phd' | 'self-study' | string, title?: string, description?: string, lanes?: string[], nodes: { id: string, label: string, term?: string, credits?: number, category?: string }[], edges?: { from: string, to: string, type?: 'prereq' | 'coreq' | 'recommended' }[] }\n"
    "Rules: (1) Do not include comments or trailing commas. (2) Use concise labels for nodes. (3) Prefer adding 'term' to group nodes by semester/phase (e.g., 'Year 1 - Fall', 'Semester 2', or for self-study 'Phase 1', 'Phase 2'). (4) Use 'edges' for prerequisite arrows only when helpful. (5) Keep JSON well-formed so the UI can parse and render it."
)


router = APIRouter(prefix="/api/threads", tags=["chat"])


# Note: Intentionally no canned content fallback; we want the LLM to respond
# based on the system prompt and the user's input. When errors occur, we
# surface an error event so the UI can prompt the user to try again.


class PostMessageBody(BaseModel):
    content: str = Field(min_length=1)
    stream: bool | None = None


@router.post("/{thread_id}/messages")
def post_message(req: Request, thread_id: str, body: PostMessageBody):
    try:
        accept_hdr = req.headers.get("accept")
    except Exception:
        accept_hdr = None
    print()
    print(f"[chat.py] POST /api/threads/{thread_id}/messages content_len={len((body.content or '').strip())}")
    thread = db.getThread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    agent = db.getAgent(thread.tenantId, thread.agentId)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    user_msg = db.addMessage(thread_id, "user", body.content)

    history = [
        {"role": m.role, "content": m.content}
        for m in db.listMessages(thread_id)
    ]

    model = agent.model or ("gpt-4o-mini")
    temperature = agent.temperature if agent.temperature is not None else 0.7

    # Streaming if requested or Accept: text/event-stream
    wants_stream = bool(body.stream) or (req.headers.get("accept") == "text/event-stream")
    print(
        f"[chat.py] thread={thread_id} agent={agent.id} model={model} temp={temperature} "
        f"history_len={len(history)} wants_stream={wants_stream} accept={accept_hdr}"
    )
    if wants_stream:
        def event_source():
            try:
                client = get_openai_client()
                # Always include plan rendering instructions so UI can visualize plans
                system_msgs = []
                if agent.systemPrompt:
                    system_msgs.append({"role": "system", "content": agent.systemPrompt})
                system_msgs.append({"role": "system", "content": PLAN_INSTRUCTIONS})
                messages = system_msgs + history
                full = ""
                emitted = False
                count = 0
                print(f"[chat.py] streaming start thread={thread_id} messages={len(messages)}")
                for delta in stream_chat_chunks(
                    client,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                ):
                    full += delta
                    if delta and delta.strip():
                        emitted = True
                    count += 1 if delta else 0
                    yield f"data: {{\"delta\": {JSONResponse(content=delta).body.decode()} }}\n\n"
                # If model produced no visible text, ask a clarifying question instead of empty
                if (not emitted) or (not full.strip()):
                    q = _build_clarifying_question(history, body.content)
                    full = q
                    print(f"[chat.py] streaming empty -> clarifying question emitted (len={len(q)})")
                    yield f"data: {{\"delta\": {JSONResponse(content=q).body.decode()} }}\n\n"
                assistant_msg = db.addMessage(thread_id, "assistant", full)
                print(
                    f"[chat.py] streaming end thread={thread_id} deltas={count} total_len={len(full)} msg_id={assistant_msg.id}"
                )
                yield f"data: {{\"done\": true, \"messageId\": \"{assistant_msg.id}\"}}\n\n"
            except Exception as e:  # pragma: no cover - stream error path
                print(f"[chat.py] streaming error thread={thread_id}: {e}")
                # Send a structured error event; UI should handle gracefully.
                yield f"data: {{\"error\": \"assistant_unavailable\"}}\n\n"

        return StreamingResponse(event_source(), media_type="text/event-stream")

    # Non-streaming
    try:
        client = get_openai_client()
        system_msgs = []
        if agent.systemPrompt:
            system_msgs.append({"role": "system", "content": agent.systemPrompt})
        system_msgs.append({"role": "system", "content": PLAN_INSTRUCTIONS})
        messages = system_msgs + history
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        text = completion.choices[0].message.content or ""
        print(
            f"[chat.py] non-stream completion thread={thread_id} text_len={len(text.strip())} messages={len(messages)}"
        )
        if not text.strip():
            text = _build_clarifying_question(history, body.content)
            print(f"[chat.py] non-stream empty -> clarifying question emitted (len={len(text)})")
        assistant_msg = db.addMessage(thread_id, "assistant", text)
        return {"userMessage": user_msg.__dict__, "assistantMessage": assistant_msg.__dict__}
    except Exception as e:
        print(f"[chat.py] non-stream error thread={thread_id}: {e}")
        raise HTTPException(status_code=502, detail=str(e))


def _build_clarifying_question(history: list[dict], prompt: str) -> str:
    """Construct a short, contextual clarifying question when the model returns no text."""
    last_user = ""
    for msg in reversed(history):
        if msg.get("role") == "user":
            last_user = (msg.get("content") or "").strip()
            break
    # Prefer the latest content (the just-posted prompt)
    if prompt and (not last_user or last_user != prompt):
        last_user = prompt.strip()
    snippet = (last_user[:120] + ("..." if len(last_user) > 120 else "")) if last_user else "your goals"
    return (
        f"Thanks for sharing about {snippet}. To tailor a study plan, could you tell me your top interests (e.g., coding, data, design, engineering, business, life sciences), any constraints (time, budget, location), and what you’ve already tried?"
    )
