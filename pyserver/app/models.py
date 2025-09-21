from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, EmailStr

ID = str


class Tenant(BaseModel):
    id: ID
    name: str
    created_at: str = Field(alias="createdAt")

    class Config:
        populate_by_name = True


class User(BaseModel):
    id: ID
    tenant_id: ID = Field(alias="tenantId")
    display_name: str = Field(alias="displayName")
    created_at: str = Field(alias="createdAt")

    class Config:
        populate_by_name = True


class Agent(BaseModel):
    id: ID
    tenant_id: ID = Field(alias="tenantId")
    name: str
    model: str
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt")
    temperature: Optional[float] = None
    created_at: str = Field(alias="createdAt")

    class Config:
        populate_by_name = True


class Thread(BaseModel):
    id: ID
    tenant_id: ID = Field(alias="tenantId")
    user_id: ID = Field(alias="userId")
    agent_id: ID = Field(alias="agentId")
    title: str
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    class Config:
        populate_by_name = True


MessageRole = Literal["system", "user", "assistant"]


class Message(BaseModel):
    id: ID
    thread_id: ID = Field(alias="threadId")
    role: MessageRole
    content: str
    created_at: str = Field(alias="createdAt")

    class Config:
        populate_by_name = True


class DBShape(BaseModel):
    tenants: list[Tenant]
    users: list[User]
    agents: list[Agent]
    threads: list[Thread]
    messages: list[Message]

class WhitelistEmail(BaseModel):
    userId: ID = Field(alias="userId")
    email: EmailStr