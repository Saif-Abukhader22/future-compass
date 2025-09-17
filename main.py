from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

app = FastAPI(title="Chat Backend")

# allow your frontend origins (no "*" if you use cookies/credentials)
ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:4000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # set True if you send cookies or Authorization headers
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Requested-With",
        "X-Tenant-Id",   # add any custom headers you use
    ],
    expose_headers=["*"],    # optional, if you need to read custom response headers
)

# ---- optional: preload a .env before spawning uvicorn ----
def _preload_env() -> Path | None:

    try:
        from dotenv import load_dotenv  # python-dotenv
    except Exception:
        return None

    here = Path(__file__).resolve()
    repo_root = here.parent
    pyserver_dir = repo_root / "pyserver"
    app_dir = pyserver_dir / "app"

    for p in (pyserver_dir / ".env", app_dir / ".env", repo_root / ".env"):
        if p.exists():
            load_dotenv(dotenv_path=p, override=True)
            # Temporary debug log: confirm env load and a few key settings (no secrets)
            try:
                mode = os.environ.get("MODE", "dev")
                host = os.environ.get("HOST", "0.0.0.0")
                port = os.environ.get("PORT", "4000")
                has_key = bool(os.environ.get("OPENAI_API_KEY"))
                print(
                    f"[debug] .env loaded from {p} | MODE={mode} | HOST={host} | PORT={port} | OPENAI_API_KEY present={has_key}"
                )
            except Exception:
                # Keep this non-fatal; it's only for temporary debugging
                pass
            return p
    return None


def _mask(s: str, keep: int = 7) -> str:
    if not s:
        return "None"
    return s[:keep] + "…"


def run(mode: str) -> int:
    # Preload env (optional; your FastAPI main also loads .env)
    loaded = _preload_env()
    print(f"[env] preloaded: {loaded}" if loaded else "[env] no preloaded .env (app will load at startup)")

    key = os.environ.get("OPENAI_API_KEY", "")
    print(f"[env] OPENAI_API_KEY present: {bool(key)} | prefix: {_mask(key)}")

    # Build uvicorn command
    app_import = "pyserver.app.main:app"
    port = int(os.environ.get("PORT", "4000"))
    # Bind to all interfaces by default so browsers/containers can reach it
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn_bin = "uvicorn.exe" if os.name == "nt" else "uvicorn"

    cmd = [
        uvicorn_bin,
        app_import,
        "--host", host,
        "--port", str(port),
    ]
    if mode == "dev":
        cmd.append("--reload")

    # Run from repo root; also ensure PYTHONPATH includes repo root
    repo_root = Path(__file__).resolve().parent
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root) + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

    try:
        print(f"[run] {' '.join(cmd)} (cwd={repo_root})")
        browse_url = f"http://localhost:{port}" if host == "0.0.0.0" else f"http://{host}:{port}"
        print(f"[run] Open {browse_url} in your browser")

        completed = subprocess.run(cmd, cwd=str(repo_root), env=env)
        return completed.returncode
    except FileNotFoundError:
        print(
            "Error: uvicorn is not installed or not in PATH.\n"
            "Install deps: pip install -r pyserver/requirements.txt",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 130


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run the FastAPI server")
    parser.add_argument(
        "--mode",
        choices=["dev", "start"],
        default=os.environ.get("MODE", "dev"),
        help="dev (default, reload) or start (no reload)",
    )
    args = parser.parse_args(argv)
    return run(args.mode)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
