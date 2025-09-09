"""
Entry point to run the FastAPI server from the repo root.

Usage:
  python main.py               # runs FastAPI with reload
  python main.py --mode start  # runs FastAPI without reload

Optional:
  Set environment variables like PORT, ALLOWED_ORIGINS, OPENAI_API_KEY before running.
  Install deps first: pip install -r pyserver/requirements.txt
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
def run(mode: str) -> int:
    app_import = "pyserver.app.main:app"
    port = int(os.environ.get("PORT", "4000"))
    # Bind to localhost by default so the browser URL works.
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn = "uvicorn.exe" if os.name == "nt" else "uvicorn"
    cmd = [
        uvicorn,
        app_import,
        "--host",
        host,
        "--port",
        str(port),
    ]
    if mode == "dev":
        cmd.append("--reload")

    try:
        print(f"Running: {' '.join(cmd)}")
        url = f"http://{host}:{port}"
        # If bound to 0.0.0.0, suggest localhost for the browser
        browse_url = f"http://localhost:{port}" if host == "0.0.0.0" else url
        print(f"Open {browse_url} in your browser")
        completed = subprocess.run(cmd)
        return completed.returncode
    except FileNotFoundError:
        print("Error: uvicorn is not installed or not in PATH.\nInstall deps: pip install -r pyserver/requirements.txt", file=sys.stderr)
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
