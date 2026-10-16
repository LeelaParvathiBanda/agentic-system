"""
FastAPI Server Entry Point with Automated LAN Access & Firewall Setup.
"""

import ctypes
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import uvicorn
from main import app

LAN_TASK_NAME = "SmartTicketAgentLAN"


def _lan_stamp_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or "."
    return Path(base) / "SmartTicketAgent" / "lan_access_stamp.txt"


def _is_windows_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _lan_task_exists() -> bool:
    try:
        res = subprocess.run(
            ["schtasks", "/Query", "/TN", LAN_TASK_NAME],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return False
    return res.returncode == 0


def _wait_for_lan_stamp(previous_mtime: float, timeout_seconds: float = 20) -> bool:
    stamp = _lan_stamp_path()
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            if stamp.exists() and stamp.stat().st_mtime > previous_mtime:
                return True
        except OSError:
            pass
        time.sleep(0.4)
    return False


def _refresh_lan_access_without_prompt() -> bool:
    """Run the already-approved firewall task. This does not show a password prompt."""
    stamp = _lan_stamp_path()
    try:
        previous_mtime = stamp.stat().st_mtime if stamp.exists() else 0
    except OSError:
        previous_mtime = 0

    try:
        started = subprocess.run(
            ["schtasks", "/Run", "/TN", LAN_TASK_NAME],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        print(f"[NOTICE] Could not refresh LAN access ({exc}).")
        return False

    if started.returncode != 0:
        detail = (started.stderr or started.stdout or "").strip()
        print(f"[NOTICE] Saved LAN task did not start. {detail}".rstrip())
        return False

    if _wait_for_lan_stamp(previous_mtime):
        print("[SUCCESS] LAN access refreshed. Other laptops can use the network URL. No admin password needed.")
        return True

    print("[NOTICE] LAN task was started, but it did not finish in time. The server will still start.")
    return False


def _run_lan_script(script_path: Path, register_task: bool) -> subprocess.CompletedProcess[str]:
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ]
    if register_task:
        command.append("-RegisterTask")
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _approve_lan_access_once(script_path: Path) -> bool:
    """Ask for the administrator password a single time and save that approval."""
    if _is_windows_admin():
        try:
            res = _run_lan_script(script_path, register_task=True)
        except Exception as exc:
            print(f"[NOTICE] Firewall setup skipped ({exc}).")
            return False
        if res.returncode == 0 and _lan_task_exists():
            print("[SUCCESS] LAN access enabled. This administrator approval will be reused automatically.")
            return True
        detail = (res.stderr or res.stdout or "").strip()
        print(f"[NOTICE] Firewall setup did not finish. {detail}".rstrip())
        return False

    print("[*] First-time LAN setup. Enter the administrator password once.")
    print("    After this, starting the server will not ask for it again.")
    safe_path = str(script_path).replace("'", "''")
    ps_cmd = (
        "$p = Start-Process -FilePath powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList "
        f"'-NoProfile','-ExecutionPolicy','Bypass','-File','{safe_path}','-RegisterTask'; "
        "if (-not $p) { exit 1 }; exit $p.ExitCode"
    )
    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as exc:
        print(f"[NOTICE] Firewall setup skipped ({exc}). The server will still start on this PC.")
        return False

    if res.returncode == 0 and _lan_task_exists():
        print("[SUCCESS] Administrator approval saved. Later server starts will not ask for the password.")
        return True

    print("[NOTICE] Administrator prompt was cancelled or setup did not finish.")
    print("         This PC can still open the app. Other laptops cannot until you approve it once.")
    return False


def ensure_lan_access() -> None:
    """
    Open TCP 8000 to other devices on the same network.

    Windows only asks for the administrator password the first time. That run
    saves an elevated scheduled task, and every later server start uses it.
    """
    if sys.platform != "win32":
        return

    script_path = Path(__file__).resolve().parent / "enable_lan_access.ps1"
    if not script_path.exists():
        print(f"[!] LAN firewall script not found at {script_path}")
        return

    if _lan_task_exists():
        print("[*] LAN access was already approved. Applying it without an admin password...")
        _refresh_lan_access_without_prompt()
        return

    _approve_lan_access_once(script_path)


def print_lan_urls(port: int = 8000) -> None:
    """Finds and displays all accessible local and LAN URLs for the server."""
    print("\n" + "=" * 65)
    print(" Smart Ticket Management Agentic System")
    print(" Local Network Access Information:")
    print(f"   * Localhost:       http://localhost:{port}")
    print(f"   * Loopback IP:     http://127.0.0.1:{port}")

    lan_ips = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                lan_ips.append(ip)
    except Exception:
        pass

    if not lan_ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127.") and ip not in lan_ips:
                lan_ips.append(ip)
        except Exception:
            pass

    for ip in lan_ips:
        print(f"   * LAN Network IP:  http://{ip}:{port}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    ensure_lan_access()
    print_lan_urls(port=8000)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
