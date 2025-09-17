from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4
import os
import sqlite3
from typing import Any


DATA_DIR = Path.cwd() / "server" / "data"
DB_FILE = DATA_DIR / "db.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Tenant:
    id: str
    name: str
    createdAt: str


@dataclass
class User:
    id: str
    tenantId: str
    displayName: str
    createdAt: str
    # Optional auth fields
    email: Optional[str] = None
    username: Optional[str] = None  # legacy
    pw_salt: Optional[str] = None
    pw_hash: Optional[str] = None
    pw_iters: Optional[int] = None
    failed_login_attempts: Optional[int] = 0
    lockout_until: Optional[str] = None
    last_login: Optional[str] = None
    # Email verification
    email_confirmed: Optional[bool] = False
    verification_code: Optional[str] = None
    verification_code_exp: Optional[str] = None


@dataclass
class Agent:
    id: str
    tenantId: str
    name: str
    model: str
    systemPrompt: Optional[str] = None
    temperature: Optional[float] = None
    createdAt: str = ""


@dataclass
class Thread:
    id: str
    tenantId: str
    userId: str
    agentId: str
    title: str
    createdAt: str
    updatedAt: str


@dataclass
class Message:
    id: str
    threadId: str
    role: str
    content: str
    createdAt: str


@dataclass
class PendingSignup:
    tenantId: str
    email: str
    displayName: str
    pw_hash: str
    code: str
    code_exp: str  # ISO exp time
    createdAt: str


def ensure_store() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_FILE.exists():
        seed = {"tenants": [], "users": [], "agents": [], "threads": [], "messages": [], "pending_signups": []}
        DB_FILE.write_text(json.dumps(seed, indent=2), encoding="utf-8")
    data = json.loads(DB_FILE.read_text(encoding="utf-8"))
    # Migrate older files lacking pending_signups
    if "pending_signups" not in data:
        data["pending_signups"] = []
        DB_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def save_store(store: dict) -> None:
    DB_FILE.write_text(json.dumps(store, indent=2), encoding="utf-8")


class FileDB:
    def upsertTenant(self, name: str, id: Optional[str] = None) -> Tenant:
        store = ensure_store()
        tenant = None
        if id is not None:
            tenant = next((t for t in store["tenants"] if t["id"] == id), None)
        if tenant is None:
            tenant = next((t for t in store["tenants"] if t["name"] == name), None)
        if tenant is None:
            tenant = Tenant(id=id or str(uuid4()), name=name, createdAt=now_iso())
            store["tenants"].append(asdict(tenant))
            save_store(store)
        return Tenant(**tenant) if isinstance(tenant, dict) else tenant

    def upsertUser(self, tenantId: str, displayName: str, id: Optional[str] = None) -> User:
        store = ensure_store()
        user = None
        if id is not None:
            user = next((u for u in store["users"] if u["id"] == id), None)
        if user is None:
            user = next((u for u in store["users"] if u["tenantId"] == tenantId and u["displayName"] == displayName), None)
        if user is None:
            user = User(id=id or str(uuid4()), tenantId=tenantId, displayName=displayName, createdAt=now_iso())
            store["users"].append(asdict(user))
            save_store(store)
        return User(**user) if isinstance(user, dict) else user

    # ---- Tenant API Keys (File backend) ----
    def _ensure_keys_bucket(self, store: dict) -> None:
        if "tenant_api_keys" not in store:
            store["tenant_api_keys"] = []

    def createTenantApiKeyRecord(self, tenantId: str, prefix: str, key_hash: str, name: Optional[str] = None, expires_at: Optional[str] = None) -> dict:
        store = ensure_store()
        self._ensure_keys_bucket(store)
        rec = {
            "id": str(uuid4()),
            "tenant_id": tenantId,
            "name": name,
            "prefix": prefix,
            "key_hash": key_hash,
            "created_at": now_iso(),
            "expires_at": expires_at,
            "revoked": 0,
        }
        # enforce unique prefix
        store["tenant_api_keys"] = [r for r in store["tenant_api_keys"] if r.get("prefix") != prefix]
        store["tenant_api_keys"].append(rec)
        save_store(store)
        return rec

    def getTenantApiKeyRecordByPrefix(self, prefix: str) -> Optional[dict]:
        store = ensure_store()
        self._ensure_keys_bucket(store)
        r = next((r for r in store["tenant_api_keys"] if r.get("prefix") == prefix), None)
        return r

    def revokeTenantApiKey(self, prefix: str) -> bool:
        store = ensure_store()
        self._ensure_keys_bucket(store)
        updated = False
        for r in store["tenant_api_keys"]:
            if r.get("prefix") == prefix:
                r["revoked"] = 1
                updated = True
        if updated:
            save_store(store)
        return updated

    def getUserByUsername(self, tenantId: str, username: str) -> Optional[User]:
        store = ensure_store()
        u = next((u for u in store["users"] if u.get("tenantId") == tenantId and (u.get("username") or "").lower() == username.lower()), None)
        return User(**u) if u else None

    def getUserByEmail(self, tenantId: str, email: str) -> Optional[User]:
        store = ensure_store()
        u = next((u for u in store["users"] if u.get("tenantId") == tenantId and (u.get("email") or "").lower() == email.lower()), None)
        return User(**u) if u else None

    def getUserById(self, userId: str) -> Optional[User]:
        store = ensure_store()
        u = next((u for u in store["users"] if u.get("id") == userId), None)
        return User(**u) if u else None

    def updateUserDisplayName(self, userId: str, displayName: str) -> Optional[User]:
        store = ensure_store()
        for u in store["users"]:
            if u["id"] == userId:
                u["displayName"] = displayName
                save_store(store)
                return User(**u)
        return None

    def createUserWithAuth(self, tenantId: str, username: str, displayName: str, pw_salt: str, pw_hash: str, pw_iters: int) -> User:
        store = ensure_store()
        # Enforce unique username within tenant
        existing = next((u for u in store["users"] if u.get("tenantId") == tenantId and (u.get("username") or "").lower() == username.lower()), None)
        if existing:
            raise ValueError("username_taken")
        user = User(
            id=str(uuid4()),
            tenantId=tenantId,
            displayName=displayName,
            createdAt=now_iso(),
            username=username,
            pw_salt=pw_salt,
            pw_hash=pw_hash,
            pw_iters=pw_iters,
        )
        store["users"].append(asdict(user))
        save_store(store)
        return user

    def createUserWithAuthEmail(self, tenantId: str, email: str, displayName: str, pw_salt: str, pw_hash: str, pw_iters: int) -> User:
        store = ensure_store()
        # Enforce unique email within tenant
        existing = next((u for u in store["users"] if u.get("tenantId") == tenantId and (u.get("email") or "").lower() == email.lower()), None)
        if existing:
            raise ValueError("email_taken")
        user = User(
            id=str(uuid4()),
            tenantId=tenantId,
            displayName=displayName,
            createdAt=now_iso(),
            email=email,
            pw_salt=pw_salt,
            pw_hash=pw_hash,
            pw_iters=pw_iters,
            failed_login_attempts=0,
            lockout_until=None,
            last_login=None,
            email_confirmed=False,
            verification_code=None,
            verification_code_exp=None,
        )
        store["users"].append(asdict(user))
        save_store(store)
        return user

    def updateUserPassword(self, userId: str, pw_salt: str, pw_hash: str, pw_iters: int) -> None:
        store = ensure_store()
        for u in store["users"]:
            if u["id"] == userId:
                u["pw_salt"] = pw_salt
                u["pw_hash"] = pw_hash
                u["pw_iters"] = pw_iters
                save_store(store)
                return

    def setUserLockout(self, userId: str, failed_attempts: int, lockout_until_iso: Optional[str]) -> None:
        store = ensure_store()
        for u in store["users"]:
            if u["id"] == userId:
                u["failed_login_attempts"] = failed_attempts
                u["lockout_until"] = lockout_until_iso
                save_store(store)
                return

    def setUserLoginSuccess(self, userId: str, last_login_iso: str) -> None:
        store = ensure_store()
        for u in store["users"]:
            if u["id"] == userId:
                u["failed_login_attempts"] = 0
                u["lockout_until"] = None
                u["last_login"] = last_login_iso
                save_store(store)
                return

    def setUserVerification(self, userId: str, code: str, exp_iso: str) -> None:
        store = ensure_store()
        for u in store["users"]:
            if u["id"] == userId:
                u["verification_code"] = code
                u["verification_code_exp"] = exp_iso
                u["email_confirmed"] = False
                save_store(store)
                return

    def confirmUserEmail(self, userId: str) -> None:
        store = ensure_store()
        for u in store["users"]:
            if u["id"] == userId:
                u["email_confirmed"] = True
                u["verification_code"] = None
                u["verification_code_exp"] = None
                save_store(store)
                return

    def listAgents(self, tenantId: str) -> list[Agent]:
        store = ensure_store()
        return [Agent(**a) for a in store["agents"] if a["tenantId"] == tenantId]

    def getAgent(self, tenantId: str, agentId: str) -> Optional[Agent]:
        store = ensure_store()
        a = next((a for a in store["agents"] if a["tenantId"] == tenantId and a["id"] == agentId), None)
        return Agent(**a) if a else None

    def createAgent(self, tenantId: str, input: dict) -> Agent:
        store = ensure_store()
        agent = Agent(id=str(uuid4()), tenantId=tenantId, createdAt=now_iso(), **input)
        store["agents"].append(asdict(agent))
        save_store(store)
        return agent

    def listThreads(self, tenantId: str, userId: str) -> list[Thread]:
        store = ensure_store()
        threads = [Thread(**t) for t in store["threads"] if t["tenantId"] == tenantId and t["userId"] == userId]
        threads.sort(key=lambda t: t.updatedAt, reverse=True)
        return threads

    def getThread(self, threadId: str) -> Optional[Thread]:
        store = ensure_store()
        t = next((t for t in store["threads"] if t["id"] == threadId), None)
        return Thread(**t) if t else None

    def createThread(self, tenantId: str, userId: str, agentId: str, title: str) -> Thread:
        store = ensure_store()
        now = now_iso()
        thread = Thread(id=str(uuid4()), tenantId=tenantId, userId=userId, agentId=agentId, title=title, createdAt=now, updatedAt=now)
        store["threads"].append(asdict(thread))
        save_store(store)
        return thread

    def updateThreadTitle(self, threadId: str, title: str) -> Optional[Thread]:
        store = ensure_store()
        updated = None
        for t in store["threads"]:
            if t["id"] == threadId:
                t["title"] = title
                t["updatedAt"] = now_iso()
                updated = Thread(**t)
                break
        if updated:
            save_store(store)
        return updated

    def listMessages(self, threadId: str) -> list[Message]:
        store = ensure_store()
        messages = [Message(**m) for m in store["messages"] if m["threadId"] == threadId]
        messages.sort(key=lambda m: m.createdAt)
        return messages

    def addMessage(self, threadId: str, role: str, content: str) -> Message:
        store = ensure_store()
        msg = Message(id=str(uuid4()), threadId=threadId, role=role, content=content, createdAt=now_iso())
        store["messages"].append(asdict(msg))
        # update thread updatedAt
        for t in store["threads"]:
            if t["id"] == threadId:
                t["updatedAt"] = now_iso()
                break
        save_store(store)
        return msg

    # ---- Pending Signups ----
    def createOrUpdatePendingSignup(self, tenantId: str, email: str, displayName: str, pw_hash: str, code: str, code_exp: str) -> PendingSignup:
        store = ensure_store()
        # Remove any existing for this tenant/email
        store["pending_signups"] = [p for p in store.get("pending_signups", []) if not (p["tenantId"] == tenantId and p["email"].lower() == email.lower())]
        ps = PendingSignup(tenantId=tenantId, email=email, displayName=displayName, pw_hash=pw_hash, code=code, code_exp=code_exp, createdAt=now_iso())
        store["pending_signups"].append(asdict(ps))
        save_store(store)
        return ps

    def getPendingSignupByEmail(self, tenantId: str, email: str) -> Optional[PendingSignup]:
        store = ensure_store()
        p = next((p for p in store.get("pending_signups", []) if p["tenantId"] == tenantId and p["email"].lower() == email.lower()), None)
        return PendingSignup(**p) if p else None

    def deletePendingSignup(self, tenantId: str, email: str) -> None:
        store = ensure_store()
        before = len(store.get("pending_signups", []))
        store["pending_signups"] = [p for p in store.get("pending_signups", []) if not (p["tenantId"] == tenantId and p["email"].lower() == email.lower())]
        if len(store.get("pending_signups", [])) != before:
            save_store(store)


# ---- SQLite backend ----

class SqliteDB:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as con:
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE,
                    created_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    display_name TEXT,
                    created_at TEXT,
                    email TEXT,
                    username TEXT,
                    pw_salt TEXT,
                    pw_hash TEXT,
                    pw_iters INTEGER,
                    failed_login_attempts INTEGER DEFAULT 0,
                    lockout_until TEXT,
                    last_login TEXT,
                    email_confirmed INTEGER DEFAULT 0,
                    verification_code TEXT,
                    verification_code_exp TEXT,
                    UNIQUE(tenant_id, email)
                )
                """
            )
            # Attempt to add columns if missing (best-effort for existing DBs)
            for stmt in [
                "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN lockout_until TEXT",
                "ALTER TABLE users ADD COLUMN last_login TEXT",
                "ALTER TABLE users ADD COLUMN email_confirmed INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN verification_code TEXT",
                "ALTER TABLE users ADD COLUMN verification_code_exp TEXT",
            ]:
                try:
                    cur.execute(stmt)
                except Exception:
                    pass
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_signups (
                    tenant_id TEXT,
                    email TEXT,
                    display_name TEXT,
                    pw_hash TEXT,
                    code TEXT,
                    code_exp TEXT,
                    created_at TEXT,
                    PRIMARY KEY (tenant_id, email)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    name TEXT,
                    model TEXT,
                    system_prompt TEXT,
                    temperature REAL,
                    created_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    user_id TEXT,
                    agent_id TEXT,
                    title TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    role TEXT,
                    content TEXT,
                    created_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_api_keys (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    name TEXT,
                    prefix TEXT UNIQUE,
                    key_hash TEXT,
                    created_at TEXT,
                    expires_at TEXT,
                    revoked INTEGER DEFAULT 0
                )
                """
            )
            con.commit()

    # ---- Tenant ----
    def upsertTenant(self, name: str, id: Optional[str] = None) -> Tenant:
        with self._conn() as con:
            cur = con.cursor()
            if id:
                cur.execute("SELECT id, name, created_at FROM tenants WHERE id=?", (id,))
                row = cur.fetchone()
                if row:
                    return Tenant(id=row[0], name=row[1], createdAt=row[2])
            cur.execute("SELECT id, name, created_at FROM tenants WHERE name=?", (name,))
            row = cur.fetchone()
            if row:
                return Tenant(id=row[0], name=row[1], createdAt=row[2])
            tid = id or str(uuid4())
            created = now_iso()
            cur.execute("INSERT INTO tenants(id, name, created_at) VALUES(?,?,?)", (tid, name, created))
            con.commit()
            return Tenant(id=tid, name=name, createdAt=created)

    # ---- Users ----
    def upsertUser(self, tenantId: str, displayName: str, id: Optional[str] = None) -> User:
        with self._conn() as con:
            cur = con.cursor()
            if id:
                cur.execute("SELECT * FROM users WHERE id=?", (id,))
                row = cur.fetchone()
                if row:
                    def _get(k, d=None):
                        try:
                            return row[k]
                        except Exception:
                            return d
                    return User(
                        id=row["id"], tenantId=row["tenant_id"], displayName=row["display_name"], createdAt=row["created_at"],
                        email=_get("email"), username=_get("username"), pw_salt=_get("pw_salt"), pw_hash=_get("pw_hash"), pw_iters=_get("pw_iters"),
                        failed_login_attempts=_get("failed_login_attempts", 0), lockout_until=_get("lockout_until"), last_login=_get("last_login"),
                    )
            cur.execute("SELECT * FROM users WHERE tenant_id=? AND display_name=?", (tenantId, displayName))
            row = cur.fetchone()
            if row:
                def _get(k, d=None):
                    try:
                        return row[k]
                    except Exception:
                        return d
                return User(
                    id=row["id"], tenantId=row["tenant_id"], displayName=row["display_name"], createdAt=row["created_at"],
                    email=_get("email"), username=_get("username"), pw_salt=_get("pw_salt"), pw_hash=_get("pw_hash"), pw_iters=_get("pw_iters"),
                    failed_login_attempts=_get("failed_login_attempts", 0), lockout_until=_get("lockout_until"), last_login=_get("last_login"),
                )
            uid = id or str(uuid4())
            created = now_iso()
            cur.execute(
                "INSERT INTO users(id, tenant_id, display_name, created_at) VALUES(?,?,?,?)",
                (uid, tenantId, displayName, created),
            )
            con.commit()
            return User(id=uid, tenantId=tenantId, displayName=displayName, createdAt=created)

    # ---- Tenant API Keys (SQLite backend) ----
    def createTenantApiKeyRecord(self, tenantId: str, prefix: str, key_hash: str, name: Optional[str] = None, expires_at: Optional[str] = None) -> dict:
        with self._conn() as con:
            cur = con.cursor()
            rid = str(uuid4())
            created = now_iso()
            cur.execute(
                """
                INSERT INTO tenant_api_keys(id, tenant_id, name, prefix, key_hash, created_at, expires_at, revoked)
                VALUES(?,?,?,?,?,?,?,0)
                ON CONFLICT(prefix) DO UPDATE SET tenant_id=excluded.tenant_id, name=excluded.name, key_hash=excluded.key_hash, created_at=excluded.created_at, expires_at=excluded.expires_at, revoked=0
                """,
                (rid, tenantId, name, prefix, key_hash, created, expires_at),
            )
            con.commit()
            return {"id": rid, "tenant_id": tenantId, "name": name, "prefix": prefix, "key_hash": key_hash, "created_at": created, "expires_at": expires_at, "revoked": 0}

    def getTenantApiKeyRecordByPrefix(self, prefix: str) -> Optional[dict]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT id, tenant_id, name, prefix, key_hash, created_at, expires_at, revoked FROM tenant_api_keys WHERE prefix=?", (prefix,))
            r = cur.fetchone()
            if not r:
                return None
            return {"id": r[0], "tenant_id": r[1], "name": r[2], "prefix": r[3], "key_hash": r[4], "created_at": r[5], "expires_at": r[6], "revoked": r[7]}

    def revokeTenantApiKey(self, prefix: str) -> bool:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE tenant_api_keys SET revoked=1 WHERE prefix=?", (prefix,))
            con.commit()
            return cur.rowcount > 0

    def getUserByEmail(self, tenantId: str, email: str) -> Optional[User]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE tenant_id=? AND lower(email)=lower(?)", (tenantId, email))
            row = cur.fetchone()
            if not row:
                return None
            def _get(k, d=None):
                try:
                    return row[k]
                except Exception:
                    return d
            return User(
                id=row["id"], tenantId=row["tenant_id"], displayName=row["display_name"], createdAt=row["created_at"],
                email=_get("email"), username=_get("username"), pw_salt=_get("pw_salt"), pw_hash=_get("pw_hash"), pw_iters=_get("pw_iters"),
                failed_login_attempts=_get("failed_login_attempts", 0), lockout_until=_get("lockout_until"), last_login=_get("last_login"),
            )

    def getUserById(self, userId: str) -> Optional[User]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE id=?", (userId,))
            row = cur.fetchone()
            if not row:
                return None
            def _get(k, d=None):
                try:
                    return row[k]
                except Exception:
                    return d
            return User(
                id=row["id"], tenantId=row["tenant_id"], displayName=row["display_name"], createdAt=row["created_at"],
                email=_get("email"), username=_get("username"), pw_salt=_get("pw_salt"), pw_hash=_get("pw_hash"), pw_iters=_get("pw_iters"),
                failed_login_attempts=_get("failed_login_attempts", 0), lockout_until=_get("lockout_until"), last_login=_get("last_login"),
            )

    def updateUserDisplayName(self, userId: str, displayName: str) -> Optional[User]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET display_name=? WHERE id=?", (displayName, userId))
            con.commit()
        return self.getUserById(userId)

    def createUserWithAuthEmail(self, tenantId: str, email: str, displayName: str, pw_salt: str, pw_hash: str, pw_iters: int) -> User:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT 1 FROM users WHERE tenant_id=? AND lower(email)=lower(?)", (tenantId, email))
            if cur.fetchone():
                raise ValueError("email_taken")
            uid = str(uuid4())
            created = now_iso()
            cur.execute(
                """
                INSERT INTO users(id, tenant_id, display_name, created_at, email, pw_salt, pw_hash, pw_iters)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (uid, tenantId, displayName, created, email, pw_salt, pw_hash, pw_iters),
            )
            con.commit()
            return User(
                id=uid, tenantId=tenantId, displayName=displayName, createdAt=created, email=email, pw_salt=pw_salt, pw_hash=pw_hash, pw_iters=pw_iters
            )

    def updateUserPassword(self, userId: str, pw_salt: str, pw_hash: str, pw_iters: int) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET pw_salt=?, pw_hash=?, pw_iters=? WHERE id=?", (pw_salt, pw_hash, pw_iters, userId))
            con.commit()

    def setUserLockout(self, userId: str, failed_attempts: int, lockout_until_iso: Optional[str]) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET failed_login_attempts=?, lockout_until=? WHERE id=?", (failed_attempts, lockout_until_iso, userId))
            con.commit()

    def setUserLoginSuccess(self, userId: str, last_login_iso: str) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET failed_login_attempts=?, lockout_until=?, last_login=? WHERE id=?", (0, None, last_login_iso, userId))
            con.commit()

    # ---- Agents ----
    def listAgents(self, tenantId: str) -> list[Agent]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM agents WHERE tenant_id=?", (tenantId,))
            rows = cur.fetchall()
            return [
                Agent(
                    id=r["id"], tenantId=r["tenant_id"], name=r["name"], model=r["model"], systemPrompt=r["system_prompt"],
                    temperature=r["temperature"], createdAt=r["created_at"],
                ) for r in rows
            ]

    def getAgent(self, tenantId: str, agentId: str) -> Optional[Agent]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM agents WHERE tenant_id=? AND id=?", (tenantId, agentId))
            r = cur.fetchone()
            if not r:
                return None
            return Agent(
                id=r["id"], tenantId=r["tenant_id"], name=r["name"], model=r["model"], systemPrompt=r["system_prompt"],
                temperature=r["temperature"], createdAt=r["created_at"],
            )

    def createAgent(self, tenantId: str, input: dict) -> Agent:
        with self._conn() as con:
            cur = con.cursor()
            aid = str(uuid4())
            created = now_iso()
            cur.execute(
                """
                INSERT INTO agents(id, tenant_id, name, model, system_prompt, temperature, created_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (aid, tenantId, input.get("name"), input.get("model"), input.get("systemPrompt"), input.get("temperature"), created),
            )
            con.commit()
            return Agent(id=aid, tenantId=tenantId, createdAt=created, **input)

    # ---- Threads ----
    def listThreads(self, tenantId: str, userId: str) -> list[Thread]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute(
                "SELECT * FROM threads WHERE tenant_id=? AND user_id=? ORDER BY updated_at DESC",
                (tenantId, userId),
            )
            rows = cur.fetchall()
            return [
                Thread(
                    id=r["id"], tenantId=r["tenant_id"], userId=r["user_id"], agentId=r["agent_id"], title=r["title"],
                    createdAt=r["created_at"], updatedAt=r["updated_at"],
                ) for r in rows
            ]

    def getThread(self, threadId: str) -> Optional[Thread]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM threads WHERE id=?", (threadId,))
            r = cur.fetchone()
            if not r:
                return None
            return Thread(
                id=r["id"], tenantId=r["tenant_id"], userId=r["user_id"], agentId=r["agent_id"], title=r["title"], createdAt=r["created_at"], updatedAt=r["updated_at"],
            )

    def createThread(self, tenantId: str, userId: str, agentId: str, title: str) -> Thread:
        with self._conn() as con:
            cur = con.cursor()
            now = now_iso()
            tid = str(uuid4())
            cur.execute(
                "INSERT INTO threads(id, tenant_id, user_id, agent_id, title, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
                (tid, tenantId, userId, agentId, title, now, now),
            )
            con.commit()
            return Thread(id=tid, tenantId=tenantId, userId=userId, agentId=agentId, title=title, createdAt=now, updatedAt=now)

    def updateThreadTitle(self, threadId: str, title: str) -> Optional[Thread]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE threads SET title=?, updated_at=? WHERE id=?", (title, now_iso(), threadId))
            con.commit()
        return self.getThread(threadId)

    # ---- Messages ----
    def listMessages(self, threadId: str) -> list[Message]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM messages WHERE thread_id=? ORDER BY created_at ASC", (threadId,))
            rows = cur.fetchall()
            return [Message(id=r["id"], threadId=r["thread_id"], role=r["role"], content=r["content"], createdAt=r["created_at"]) for r in rows]

    def addMessage(self, threadId: str, role: str, content: str) -> Message:
        with self._conn() as con:
            cur = con.cursor()
            mid = str(uuid4())
            created = now_iso()
            cur.execute("INSERT INTO messages(id, thread_id, role, content, created_at) VALUES(?,?,?,?,?)", (mid, threadId, role, content, created))
            cur.execute("UPDATE threads SET updated_at=? WHERE id=?", (now_iso(), threadId))
            con.commit()
            return Message(id=mid, threadId=threadId, role=role, content=content, createdAt=created)

    # ---- Pending Signups ----
    def createOrUpdatePendingSignup(self, tenantId: str, email: str, displayName: str, pw_hash: str, code: str, code_exp: str) -> PendingSignup:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO pending_signups(tenant_id, email, display_name, pw_hash, code, code_exp, created_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id, email) DO UPDATE SET display_name=excluded.display_name, pw_hash=excluded.pw_hash, code=excluded.code, code_exp=excluded.code_exp, created_at=excluded.created_at
                """,
                (tenantId, email, displayName, pw_hash, code, code_exp, now_iso()),
            )
            con.commit()
            return PendingSignup(tenantId=tenantId, email=email, displayName=displayName, pw_hash=pw_hash, code=code, code_exp=code_exp, createdAt=now_iso())

    def getPendingSignupByEmail(self, tenantId: str, email: str) -> Optional[PendingSignup]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT tenant_id, email, display_name, pw_hash, code, code_exp, created_at FROM pending_signups WHERE tenant_id=? AND lower(email)=lower(?)", (tenantId, email))
            r = cur.fetchone()
            if not r:
                return None
            return PendingSignup(tenantId=r[0], email=r[1], displayName=r[2], pw_hash=r[3], code=r[4], code_exp=r[5], createdAt=r[6])

    def deletePendingSignup(self, tenantId: str, email: str) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM pending_signups WHERE tenant_id=? AND lower(email)=lower(?)", (tenantId, email))
            con.commit()


def get_db():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Postgres
        if db_url.startswith("postgres://") or db_url.startswith("postgresql://"):
            try:
                return PostgresDB(db_url)
            except Exception as e:
                raise RuntimeError(f"Failed to init PostgresDB: {e}")
        # SQLite DSN
        if db_url.startswith("sqlite///") or db_url.startswith("sqlite:///"):
            path = db_url.split("sqlite:///")[-1]
            return SqliteDB(path)
        # SQLite file
        if db_url.endswith(".db"):
            return SqliteDB(db_url)
    if os.getenv("USE_SQLITE") == "1":
        default_path = DATA_DIR / "app.db"
        return SqliteDB(default_path)
    return FileDB()

# ---- PostgreSQL backend ----

class PostgresDB:
    def __init__(self, dsn: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except Exception as e:  # pragma: no cover - import error path
            raise RuntimeError(
                "psycopg is not installed. Add 'psycopg[binary]' to requirements and install."
            ) from e
        self._psycopg = psycopg
        self._dict_row = dict_row
        self.dsn = dsn
        self._init()

    def _conn(self):
        return self._psycopg.connect(self.dsn, row_factory=self._dict_row)

    def _init(self):
        with self._conn() as con:
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE,
                    created_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    display_name TEXT,
                    created_at TEXT,
                    email TEXT,
                    username TEXT,
                    pw_salt TEXT,
                    pw_hash TEXT,
                    pw_iters INTEGER,
                    failed_login_attempts INTEGER DEFAULT 0,
                    lockout_until TEXT,
                    last_login TEXT,
                    email_confirmed INTEGER DEFAULT 0,
                    verification_code TEXT,
                    verification_code_exp TEXT,
                    UNIQUE(tenant_id, email)
                )
                """
            )
            # Add columns if not exist (Postgres)
            try:
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS lockout_until TEXT")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TEXT")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_confirmed INTEGER DEFAULT 0")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code TEXT")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code_exp TEXT")
            except Exception:
                pass
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_signups (
                    tenant_id TEXT,
                    email TEXT,
                    display_name TEXT,
                    pw_hash TEXT,
                    code TEXT,
                    code_exp TEXT,
                    created_at TEXT,
                    PRIMARY KEY (tenant_id, email)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    name TEXT,
                    model TEXT,
                    system_prompt TEXT,
                    temperature REAL,
                    created_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    user_id TEXT,
                    agent_id TEXT,
                    title TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    role TEXT,
                    content TEXT,
                    created_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_api_keys (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    name TEXT,
                    prefix TEXT UNIQUE,
                    key_hash TEXT,
                    created_at TEXT,
                    expires_at TEXT,
                    revoked INTEGER DEFAULT 0
                )
                """
            )
            con.commit()

    # ---- Tenant ----
    def upsertTenant(self, name: str, id: Optional[str] = None) -> Tenant:
        with self._conn() as con:
            cur = con.cursor()
            if id:
                cur.execute("SELECT id, name, created_at FROM tenants WHERE id=%s", (id,))
                row = cur.fetchone()
                if row:
                    return Tenant(id=row["id"], name=row["name"], createdAt=row["created_at"])
            cur.execute("SELECT id, name, created_at FROM tenants WHERE name=%s", (name,))
            row = cur.fetchone()
            if row:
                return Tenant(id=row["id"], name=row["name"], createdAt=row["created_at"])
            tid = id or str(uuid4())
            created = now_iso()
            cur.execute("INSERT INTO tenants(id, name, created_at) VALUES(%s,%s,%s)", (tid, name, created))
            con.commit()
            return Tenant(id=tid, name=name, createdAt=created)

    # ---- Users ----
    def upsertUser(self, tenantId: str, displayName: str, id: Optional[str] = None) -> User:
        with self._conn() as con:
            cur = con.cursor()
            if id:
                cur.execute("SELECT * FROM users WHERE id=%s", (id,))
                row = cur.fetchone()
                if row:
                    return User(
                        id=row["id"], tenantId=row["tenant_id"], displayName=row["display_name"], createdAt=row["created_at"],
                        email=row.get("email"), username=row.get("username"), pw_salt=row.get("pw_salt"), pw_hash=row.get("pw_hash"), pw_iters=row.get("pw_iters"),
                        failed_login_attempts=row.get("failed_login_attempts", 0), lockout_until=row.get("lockout_until"), last_login=row.get("last_login"),
                        email_confirmed=bool(row.get("email_confirmed", 0)), verification_code=row.get("verification_code"), verification_code_exp=row.get("verification_code_exp"),
                    )
            cur.execute("SELECT * FROM users WHERE tenant_id=%s AND display_name=%s", (tenantId, displayName))
            row = cur.fetchone()
            if row:
                return User(
                    id=row["id"], tenantId=row["tenant_id"], displayName=row["display_name"], createdAt=row["created_at"],
                    email=row.get("email"), username=row.get("username"), pw_salt=row.get("pw_salt"), pw_hash=row.get("pw_hash"), pw_iters=row.get("pw_iters"),
                    failed_login_attempts=row.get("failed_login_attempts", 0), lockout_until=row.get("lockout_until"), last_login=row.get("last_login"),
                    email_confirmed=bool(row.get("email_confirmed", 0)), verification_code=row.get("verification_code"), verification_code_exp=row.get("verification_code_exp"),
                )
            uid = id or str(uuid4())
            created = now_iso()
            cur.execute(
                "INSERT INTO users(id, tenant_id, display_name, created_at) VALUES(%s,%s,%s,%s)",
                (uid, tenantId, displayName, created),
            )
            con.commit()
            return User(id=uid, tenantId=tenantId, displayName=displayName, createdAt=created)

    def getUserByEmail(self, tenantId: str, email: str) -> Optional[User]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE tenant_id=%s AND lower(email)=lower(%s)", (tenantId, email))
            row = cur.fetchone()
            if not row:
                return None
            return User(
                id=row["id"], tenantId=row["tenant_id"], displayName=row["display_name"], createdAt=row["created_at"],
                email=row.get("email"), username=row.get("username"), pw_salt=row.get("pw_salt"), pw_hash=row.get("pw_hash"), pw_iters=row.get("pw_iters"),
                failed_login_attempts=row.get("failed_login_attempts", 0), lockout_until=row.get("lockout_until"), last_login=row.get("last_login"),
                email_confirmed=bool(row.get("email_confirmed", 0)), verification_code=row.get("verification_code"), verification_code_exp=row.get("verification_code_exp"),
            )

    def createUserWithAuthEmail(self, tenantId: str, email: str, displayName: str, pw_salt: str, pw_hash: str, pw_iters: int) -> User:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT 1 FROM users WHERE tenant_id=%s AND lower(email)=lower(%s)", (tenantId, email))
            if cur.fetchone():
                raise ValueError("email_taken")
            uid = str(uuid4())
            created = now_iso()
            cur.execute(
                """
                INSERT INTO users(id, tenant_id, display_name, created_at, email, pw_salt, pw_hash, pw_iters)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (uid, tenantId, displayName, created, email, pw_salt, pw_hash, pw_iters),
            )
            con.commit()
            return User(
                id=uid, tenantId=tenantId, displayName=displayName, createdAt=created, email=email, pw_salt=pw_salt, pw_hash=pw_hash, pw_iters=pw_iters
            )

    def updateUserPassword(self, userId: str, pw_salt: str, pw_hash: str, pw_iters: int) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET pw_salt=%s, pw_hash=%s, pw_iters=%s WHERE id=%s", (pw_salt, pw_hash, pw_iters, userId))
            con.commit()

    def setUserLockout(self, userId: str, failed_attempts: int, lockout_until_iso: Optional[str]) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET failed_login_attempts=%s, lockout_until=%s WHERE id=%s", (failed_attempts, lockout_until_iso, userId))
            con.commit()

    def setUserLoginSuccess(self, userId: str, last_login_iso: str) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET failed_login_attempts=%s, lockout_until=%s, last_login=%s WHERE id=%s", (0, None, last_login_iso, userId))
            con.commit()
    def setUserVerification(self, userId: str, code: str, exp_iso: str) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET verification_code=%s, verification_code_exp=%s, email_confirmed=%s WHERE id=%s", (code, exp_iso, 0, userId))
            con.commit()
    def confirmUserEmail(self, userId: str) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET email_confirmed=%s, verification_code=NULL, verification_code_exp=NULL WHERE id=%s", (1, userId))
            con.commit()

    # ---- Agents ----
    def listAgents(self, tenantId: str) -> list[Agent]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM agents WHERE tenant_id=%s", (tenantId,))
            rows = cur.fetchall()
            return [
                Agent(
                    id=r["id"], tenantId=r["tenant_id"], name=r["name"], model=r["model"], systemPrompt=r["system_prompt"],
                    temperature=r["temperature"], createdAt=r["created_at"],
                ) for r in rows
            ]

    def getAgent(self, tenantId: str, agentId: str) -> Optional[Agent]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM agents WHERE tenant_id=%s AND id=%s", (tenantId, agentId))
            r = cur.fetchone()
            if not r:
                return None
            return Agent(
                id=r["id"], tenantId=r["tenant_id"], name=r["name"], model=r["model"], systemPrompt=r["system_prompt"],
                temperature=r["temperature"], createdAt=r["created_at"],
            )

    def createAgent(self, tenantId: str, input: dict) -> Agent:
        with self._conn() as con:
            cur = con.cursor()
            aid = str(uuid4())
            created = now_iso()
            cur.execute(
                """
                INSERT INTO agents(id, tenant_id, name, model, system_prompt, temperature, created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s)
                """,
                (aid, tenantId, input.get("name"), input.get("model"), input.get("systemPrompt"), input.get("temperature"), created),
            )
            con.commit()
            return Agent(id=aid, tenantId=tenantId, createdAt=created, **input)

    # ---- Threads ----
    def listThreads(self, tenantId: str, userId: str) -> list[Thread]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute(
                "SELECT * FROM threads WHERE tenant_id=%s AND user_id=%s ORDER BY updated_at DESC",
                (tenantId, userId),
            )
            rows = cur.fetchall()
            return [
                Thread(
                    id=r["id"], tenantId=r["tenant_id"], userId=r["user_id"], agentId=r["agent_id"], title=r["title"],
                    createdAt=r["created_at"], updatedAt=r["updated_at"],
                ) for r in rows
            ]

    def getThread(self, threadId: str) -> Optional[Thread]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM threads WHERE id=%s", (threadId,))
            r = cur.fetchone()
            if not r:
                return None
            return Thread(
                id=r["id"], tenantId=r["tenant_id"], userId=r["user_id"], agentId=r["agent_id"], title=r["title"], createdAt=r["created_at"], updatedAt=r["updated_at"],
            )

    def createThread(self, tenantId: str, userId: str, agentId: str, title: str) -> Thread:
        with self._conn() as con:
            cur = con.cursor()
            now = now_iso()
            tid = str(uuid4())
            cur.execute(
                "INSERT INTO threads(id, tenant_id, user_id, agent_id, title, created_at, updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (tid, tenantId, userId, agentId, title, now, now),
            )
            con.commit()
            return Thread(id=tid, tenantId=tenantId, userId=userId, agentId=agentId, title=title, createdAt=now, updatedAt=now)

    def updateThreadTitle(self, threadId: str, title: str) -> Optional[Thread]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE threads SET title=%s, updated_at=%s WHERE id=%s", (title, now_iso(), threadId))
            con.commit()
        return self.getThread(threadId)

    # ---- Messages ----
    def listMessages(self, threadId: str) -> list[Message]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM messages WHERE thread_id=%s ORDER BY created_at ASC", (threadId,))
            rows = cur.fetchall()
            return [Message(id=r["id"], threadId=r["thread_id"], role=r["role"], content=r["content"], createdAt=r["created_at"]) for r in rows]

    def addMessage(self, threadId: str, role: str, content: str) -> Message:
        with self._conn() as con:
            cur = con.cursor()
            mid = str(uuid4())
            created = now_iso()
            cur.execute("INSERT INTO messages(id, thread_id, role, content, created_at) VALUES(%s,%s,%s,%s,%s)", (mid, threadId, role, content, created))
            cur.execute("UPDATE threads SET updated_at=%s WHERE id=%s", (now_iso(), threadId))
            con.commit()
            return Message(id=mid, threadId=threadId, role=role, content=content, createdAt=created)

    # ---- Pending Signups ----
    def createOrUpdatePendingSignup(self, tenantId: str, email: str, displayName: str, pw_hash: str, code: str, code_exp: str) -> PendingSignup:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO pending_signups(tenant_id, email, display_name, pw_hash, code, code_exp, created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_id, email)
                DO UPDATE SET display_name=excluded.display_name, pw_hash=excluded.pw_hash, code=excluded.code, code_exp=excluded.code_exp, created_at=excluded.created_at
                """,
                (tenantId, email, displayName, pw_hash, code, code_exp, now_iso()),
            )
            con.commit()
            return PendingSignup(tenantId=tenantId, email=email, displayName=displayName, pw_hash=pw_hash, code=code, code_exp=code_exp, createdAt=now_iso())

    def getPendingSignupByEmail(self, tenantId: str, email: str) -> Optional[PendingSignup]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT tenant_id, email, display_name, pw_hash, code, code_exp, created_at FROM pending_signups WHERE tenant_id=%s AND lower(email)=lower(%s)", (tenantId, email))
            r = cur.fetchone()
            if not r:
                return None
            return PendingSignup(tenantId=r[0], email=r[1], displayName=r[2], pw_hash=r[3], code=r[4], code_exp=r[5], createdAt=r[6])

    def deletePendingSignup(self, tenantId: str, email: str) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM pending_signups WHERE tenant_id=%s AND lower(email)=lower(%s)", (tenantId, email))
            con.commit()

    # ---- Tenant API Keys (Postgres backend) ----
    def createTenantApiKeyRecord(self, tenantId: str, prefix: str, key_hash: str, name: Optional[str] = None, expires_at: Optional[str] = None) -> dict:
        with self._conn() as con:
            cur = con.cursor()
            rid = str(uuid4())
            created = now_iso()
            cur.execute(
                """
                INSERT INTO tenant_api_keys(id, tenant_id, name, prefix, key_hash, created_at, expires_at, revoked)
                VALUES(%s,%s,%s,%s,%s,%s,%s,0)
                ON CONFLICT (prefix) DO UPDATE SET tenant_id=excluded.tenant_id, name=excluded.name, key_hash=excluded.key_hash, created_at=excluded.created_at, expires_at=excluded.expires_at, revoked=0
                """,
                (rid, tenantId, name, prefix, key_hash, created, expires_at),
            )
            con.commit()
            return {"id": rid, "tenant_id": tenantId, "name": name, "prefix": prefix, "key_hash": key_hash, "created_at": created, "expires_at": expires_at, "revoked": 0}

    def getTenantApiKeyRecordByPrefix(self, prefix: str) -> Optional[dict]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT id, tenant_id, name, prefix, key_hash, created_at, expires_at, revoked FROM tenant_api_keys WHERE prefix=%s", (prefix,))
            r = cur.fetchone()
            if not r:
                return None
            # For psycopg dict_row, r[...] works by key; for row tuple, index works. Support both.
            def getv(x):
                try:
                    return r[x]
                except Exception:
                    return None
            return {
                "id": getv("id") or r[0],
                "tenant_id": getv("tenant_id") or r[1],
                "name": getv("name") or r[2],
                "prefix": getv("prefix") or r[3],
                "key_hash": getv("key_hash") or r[4],
                "created_at": getv("created_at") or r[5],
                "expires_at": getv("expires_at") or r[6],
                "revoked": getv("revoked") or r[7],
            }

    def revokeTenantApiKey(self, prefix: str) -> bool:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE tenant_api_keys SET revoked=1 WHERE prefix=%s", (prefix,))
            con.commit()
            return cur.rowcount > 0

    # ---- Users helpers (Postgres) ----
    def getUserById(self, userId: str) -> Optional[User]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE id=%s", (userId,))
            r = cur.fetchone()
            if not r:
                return None
            def _get(k, d=None):
                try:
                    return r[k]
                except Exception:
                    return d
            return User(
                id=r["id"], tenantId=r["tenant_id"], displayName=r["display_name"], createdAt=r["created_at"],
                email=_get("email"), username=_get("username"), pw_salt=_get("pw_salt"), pw_hash=_get("pw_hash"), pw_iters=_get("pw_iters"),
                failed_login_attempts=_get("failed_login_attempts", 0), lockout_until=_get("lockout_until"), last_login=_get("last_login"),
            )

    def updateUserDisplayName(self, userId: str, displayName: str) -> Optional[User]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET display_name=%s WHERE id=%s", (displayName, userId))
            con.commit()
        return self.getUserById(userId)


# Select the database backend at import time
db = get_db()
