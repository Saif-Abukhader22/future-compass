from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from ..db import db


router = APIRouter(prefix="/api/agents", tags=["agents"])


class CreateAgentBody(BaseModel):
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    systemPrompt: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)


@router.get("/")
def list_agents(req: Request):
    tenant_id = req.state.tenant_id
    agents = [a.__dict__ for a in db.listAgents(tenant_id)]
    return {"agents": agents}


@router.post("/", status_code=201)
def create_agent(req: Request, body: CreateAgentBody):
    tenant_id = req.state.tenant_id
    agent = db.createAgent(tenant_id, body.model_dump())
    return {"agent": agent.__dict__}

