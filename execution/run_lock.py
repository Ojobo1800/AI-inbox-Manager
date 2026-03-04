"""
Run lock protection for process_inbox_auto.py.

Prevents concurrent execution to avoid:
- Double Gmail mutations (move/delete)
- GPT API cost spikes
- Race conditions in external systems

Lock file: tmp/process.lock (JSON with PID, start time, triggered_by)
Stale lock timeout: 20 minutes — after this, any lock is considered dead.

Usage:
    from run_lock import acquire_lock, release_lock

    if not acquire_lock(triggered_by="scheduled"):
        sys.exit(2)  # already running
    try:
        ...
    finally:
        release_lock()
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# If a lock is older than this, it is considered stale even if the PID exists
STALE_LOCK_TIMEOUT_SECONDS = 1200  # 20 minutes


def _lock_path() -> Path:
    project_root = Path(__file__).parent.parent
    lock_dir = project_root / "tmp"
    lock_dir.mkdir(exist_ok=True)
    return lock_dir / "process.lock"


def _pid_running(pid: int) -> bool:
    """Return True if a process with this PID is alive on the current OS."""
    try:
        # os.kill(pid, 0) works on both Unix and Windows:
        # raises OSError if the process does not exist or permission denied.
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def _read_lock() -> Optional[Dict[str, Any]]:
    """Read and parse the lock file. Returns None on any error."""
    path = _lock_path()
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def acquire_lock(triggered_by: str = "unknown") -> bool:
    """
    Try to acquire the run lock.

    If an existing lock is found, checks whether the owning process is still
    alive and whether the lock is within the stale timeout.  Stale locks are
    automatically cleared.

    Args:
        triggered_by: Label for who is starting the run (e.g. "scheduled",
                       "manual", username from dashboard).

    Returns:
        True  — lock acquired, caller may proceed.
        False — another run is already active, caller must abort.
    """
    path = _lock_path()
    existing = _read_lock()

    if existing:
        pid = existing.get("pid")
        started_str = existing.get("started_at", "")
        by = existing.get("triggered_by", "?")

        alive = pid and _pid_running(int(pid))

        elapsed = None
        if started_str:
            try:
                started = datetime.fromisoformat(started_str)
                elapsed = (datetime.utcnow() - started).total_seconds()
            except Exception:
                pass

        if alive and (elapsed is None or elapsed < STALE_LOCK_TIMEOUT_SECONDS):
            logger.warning(
                f"Run lock active — PID={pid}, triggered_by={by}, "
                f"started={started_str}, elapsed={elapsed:.0f}s"
            )
            return False  # live lock — do not proceed

        # Stale lock (dead PID or timed out) — clear it
        reason = "dead PID" if not alive else f"exceeded {STALE_LOCK_TIMEOUT_SECONDS}s timeout"
        logger.warning(f"Clearing stale lock ({reason}): PID={pid}, started={started_str}")
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

    # Write new lock
    lock_data: Dict[str, Any] = {
        "pid": os.getpid(),
        "started_at": datetime.utcnow().isoformat(),
        "triggered_by": triggered_by,
    }
    try:
        with open(path, "w") as f:
            json.dump(lock_data, f)
        logger.info(f"Run lock acquired (PID={os.getpid()}, triggered_by={triggered_by})")
        return True
    except Exception as e:
        # If we cannot write the lock file, log a warning but don't block the run.
        # Better to run without a lock than to silently drop all processing.
        logger.error(f"Failed to write lock file — proceeding without lock: {e}")
        return True


def release_lock() -> None:
    """
    Release the lock by deleting the lock file.

    Only deletes the file if its PID matches the current process, to avoid
    accidentally releasing a lock acquired by a different run.
    """
    path = _lock_path()
    existing = _read_lock()
    if existing is None:
        return  # nothing to release

    if existing.get("pid") == os.getpid():
        try:
            path.unlink(missing_ok=True)
            logger.info("Run lock released")
        except Exception as e:
            logger.warning(f"Failed to delete lock file: {e}")
    else:
        logger.warning(
            f"Skipping lock release — lock owned by PID={existing.get('pid')}, "
            f"we are PID={os.getpid()}"
        )


def get_lock_info() -> Optional[Dict[str, Any]]:
    """
    Return current lock status, or None if no active lock exists.

    Stale locks (dead PID) are treated as unlocked.

    Returns:
        Dict with keys: pid, started_at, triggered_by, elapsed_seconds
        None if unlocked.
    """
    existing = _read_lock()
    if existing is None:
        return None

    pid = existing.get("pid")
    started_str = existing.get("started_at", "")

    if pid and not _pid_running(int(pid)):
        return None  # stale lock — report as unlocked

    elapsed = 0.0
    if started_str:
        try:
            started = datetime.fromisoformat(started_str)
            elapsed = (datetime.utcnow() - started).total_seconds()
        except Exception:
            pass

    return {
        "pid": pid,
        "started_at": started_str,
        "triggered_by": existing.get("triggered_by", "unknown"),
        "elapsed_seconds": round(elapsed, 1),
    }
