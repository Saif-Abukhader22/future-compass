from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..db import db


router = APIRouter(prefix="/api/threads", tags=["threads"])


class CreateThreadBody(BaseModel):
    agentId: str = Field(min_length=1)
    title: str = Field(default="New Chat", min_length=1)

class UpdateThreadBody(BaseModel):
    title: str = Field(min_length=1)

@router.get("/")
def list_threads(req: Request):
    tenant_id = req.state.tenant_id
    user_id = req.state.user_id
    threads = [t.__dict__ for t in db.listThreads(tenant_id, user_id)]
    return {"threads": threads}


@router.post("/", status_code=201)
def create_thread(req: Request, body: CreateThreadBody):
    tenant_id = req.state.tenant_id
    user_id = req.state.user_id
    agent = db.getAgent(tenant_id, body.agentId)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    thread = db.createThread(tenant_id, user_id, body.agentId, body.title)
    return {"thread": thread.__dict__}


@router.get("/{thread_id}")
def get_thread(thread_id: str):
    thread = db.getThread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"thread": thread.__dict__}


@router.patch("/{thread_id}")
def update_thread(thread_id: str, body: UpdateThreadBody):
    thread = db.getThread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    updated = db.updateThreadTitle(thread_id, body.title)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update thread")
    return {"thread": updated.__dict__}


@router.get("/{thread_id}/messages")
def list_messages(thread_id: str):
    thread = db.getThread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    messages = [m.__dict__ for m in db.listMessages(thread_id)]
    return {"messages": messages}
