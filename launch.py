#!/usr/bin/env python3
"""
QADIR — Application Launcher
Starts the backend server and opens the frontend in a browser.

Usage:
    python launch.py              # Start on default port 8900
    python launch.py --port 9000  # Start on custom port
    python launch.py --no-open    # Start without opening browser
"""

import sys
import os
import time
import signal
import subprocess
import webbrowser
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent
BACKEND_DIR = BASE_DIR / "backend"

def check_dependencies():
    """Check if required packages are installed."""
    required = ["fastapi", "uvicorn", "anthropic", "openai", "yaml"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"📦 Installing missing packages: {', '.join(missing)}")
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r",
            str(BASE_DIR / "requirements.txt"), "-q"
        ], check=True)
        print("✅ Dependencies installed")

def check_api_keys():
    """Check if at least one API key is configured."""
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.exists():
        with open(env_file) as f:
            content = f.read()
            keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
                    "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY"]
            found = [k for k in keys if k in content and content.split(k + "=")[1].split("\n")[0].strip()]
            if found:
                print(f"🔑 Found API keys: {', '.join(found)}")
                return True

    print("⚠️  No API keys found. Add keys in Settings after launching.")
    return False

def start_server(port: int):
    """Start the FastAPI server."""
    print(f"\n{'='*50}")
    print(f"  🧠 QADIR — AI Agent Framework")
    print(f"  Version: 0.1.0")
    print(f"  Protocol: NZT-8200")
    print(f"  Port: {port}")
    print(f"{'='*50}\n")

    # Start uvicorn
    os.chdir(str(BASE_DIR))
    cmd = [
        sys.executable, "-m", "uvicorn",
        "backend.app:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--log-level", "warning",
    ]

    process = subprocess.Popen(cmd)

    # Wait for server to start
    time.sleep(2)

    return process

def open_browser(port: int):
    """Open the application in the default browser."""
    url = f"http://localhost:{port}"
    print(f"🌐 Opening {url}")
    webbrowser.open(url)

def main():
    parser = argparse.ArgumentParser(description="QADIR — AI Agent Framework")
    parser.add_argument("--port", type=int, default=8900, help="Port to run on")
    parser.add_argument("--no-open", action="store_true", help="Don't open browser")
    args = parser.parse_args()

    print("🧠 QADIR — Starting up...\n")

    # Check dependencies
    check_dependencies()

    # Check API keys
    check_api_keys()

    # Start server
    process = start_server(args.port)

    # Open browser
    if not args.no_open:
        open_browser(args.port)

    print(f"\n✅ QADIR is running at http://localhost:{args.port}")
    print("Press Ctrl+C to stop.\n")

    # Handle shutdown
    def signal_handler(sig, frame):
        print("\n\n👋 Qadir shutting down. .")
        process.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep running
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\n\n👋 Qadir shutting down. .")
        process.terminate()

if __name__ == "__main__":
    main()
