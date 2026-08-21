#!/usr/bin/env python3
"""Permanent external supervisor for the Soroush Plus bot.

Run this file instead of running ``main.py`` directly.  The supervisor is a
separate process: it captures process-terminating tracebacks, writes a complete
crash report under the runtime ``logs`` directory, queues one private owner
notification, and restarts the bot with bounded exponential backoff.

Normal messages and normal bot activity never enter this code.  A report is
created only after the child process exits unexpectedly or cannot be started.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from dotenv import load_dotenv

from modules.runtime_paths import PROJECT_ROOT, runtime_config_file, runtime_log_file
from modules.time_utils import now_local
from modules.watchdog_reporting import (
    deliver_with_fresh_client,
    pending_count,
    queue_incident,
)


LOG_FILE = runtime_log_file("watchdog.log")
LOCK_FILE = runtime_config_file("watchdog.lock", migrate=False)
_FRAME_RE = re.compile(
    r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+)',
    re.MULTILINE,
)
_SECRET_PATTERNS = (
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "<redacted-github-token>"),
    (
        re.compile(
            r"(?i)\b(SOROUSH_SESSION_STRING|BOT_TOKEN|SOROUSH_BOT_TOKEN|API_HASH)"
            r"\s*=\s*([^\s]+)"
        ),
        r"\1=<redacted>",
    ),
)


@dataclass
class ChildResult:
    command: List[str]
    pid: int
    returncode: int
    started_at: float
    ended_at: float
    stderr_tail: str
    traceback_text: str

    @property
    def uptime_seconds(self) -> float:
        return max(0.0, self.ended_at - self.started_at)


class StderrCapture:
    """Tee stderr while retaining the complete last traceback chain."""

    def __init__(self, recent_lines: int = 250):
        self._recent = deque(maxlen=max(20, int(recent_lines)))
        self._active: Optional[List[str]] = None
        self._candidate: List[str] = []
        self._chain_bridge: List[str] = []
        self._bridge_open = False
        self._lock = threading.Lock()

    @staticmethod
    def _is_traceback_start(line: str) -> bool:
        return line.lstrip().startswith("Traceback (most recent call last):")

    @staticmethod
    def _is_syntax_frame_start(line: str) -> bool:
        return bool(_FRAME_RE.match(line))

    @staticmethod
    def _is_exception_line(line: str) -> bool:
        cleaned = line.strip().lstrip("|+- ").strip()
        if cleaned in {"KeyboardInterrupt", "SystemExit"}:
            return True
        # Final Python exception lines are not source-indented and contain a
        # qualified exception class followed by a colon.  This also accepts
        # custom exception names that do not end in "Error".
        return bool(re.match(r"^[A-Za-z_][\w.]*:\s*.*$", cleaned))

    @staticmethod
    def _is_chain_marker(line: str) -> bool:
        text = line.strip()
        return (
            "During handling of the above exception" in text
            or "The above exception was the direct cause" in text
        )

    def feed(self, line: str) -> None:
        with self._lock:
            self._recent.append(line)
            if self._is_traceback_start(line):
                if self._bridge_open and self._chain_bridge:
                    self._active = list(self._chain_bridge) + [line]
                else:
                    self._active = [line]
                self._bridge_open = False
                return

            # Syntax/import compilation failures may start directly with a
            # ``File ..., line ...`` frame and have no Traceback header.
            if self._active is None and self._is_syntax_frame_start(line):
                self._active = [line]
                self._bridge_open = False
                return

            if self._active is not None:
                self._active.append(line)
                if self._is_exception_line(line):
                    self._candidate = list(self._active)
                    self._chain_bridge = list(self._active)
                    self._active = None
                    self._bridge_open = True
                return

            if self._bridge_open:
                if not line.strip() or self._is_chain_marker(line):
                    self._chain_bridge.append(line)
                    return
                # An unrelated stderr line means the completed traceback was
                # handled and should not absorb future runtime logs.
                self._bridge_open = False
                self._chain_bridge = []

    def result(self) -> Dict[str, str]:
        with self._lock:
            if self._active:
                traceback_lines = list(self._active)
            else:
                traceback_lines = list(self._candidate)
            recent = list(self._recent)
        return {
            "traceback": "".join(traceback_lines).strip(),
            "recent": "".join(recent).strip(),
        }


def _redact(text: str) -> str:
    value = text or ""
    for pattern, replacement in _SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return max(minimum, float(default))


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return max(minimum, int(default))


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("soroush.watchdog")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        str(LOG_FILE),
        maxBytes=_env_int("WATCHDOG_LOG_MAX_BYTES", 2 * 1024 * 1024),
        backupCount=_env_int("WATCHDOG_LOG_BACKUPS", 5),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    ))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class ReporterLoggerAdapter:
    """Expose the logger interface used by the bot's reporting helper."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log_info(self, message: str) -> None:
        self.logger.info(message)

    def log_error(self, message: str) -> None:
        self.logger.error(message)


class SingleInstance:
    """Keep two launch scripts from supervising the same bot concurrently."""

    def __init__(self, path: Path):
        self.path = path
        self.stream = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+", encoding="utf-8")
        try:
            import fcntl
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            # Termux/Linux has fcntl.  On other platforms the PID text is still
            # useful, but advisory locking may not be available.
            pass
        except OSError as error:
            raise RuntimeError("another watchdog instance is already running") from error
        self.stream.seek(0)
        self.stream.truncate()
        self.stream.write(str(os.getpid()))
        self.stream.flush()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def close(self) -> None:
        if self.stream is None:
            return
        try:
            import fcntl
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        self.stream.close()
        self.stream = None


def _terminate_process(process: subprocess.Popen, logger: logging.Logger) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
    except Exception as error:
        logger.error("WATCHDOG CHILD TERMINATE FAILED pid=%s error=%r", process.pid, error)
        return
    try:
        process.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass


def run_child(
    command: Sequence[str],
    stop_event: threading.Event,
    logger: Optional[logging.Logger] = None,
) -> ChildResult:
    """Run and monitor one child process, returning only after it exits."""
    logger = logger or setup_logger()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["SOROUSH_WATCHDOG_CHILD"] = "1"
    started = time.time()
    process = subprocess.Popen(
        list(command),
        cwd=str(PROJECT_ROOT),
        env=env,
        stdin=None,
        stdout=None,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        start_new_session=(os.name == "posix"),
    )
    logger.info(
        "WATCHDOG CHILD START pid=%s command=%s",
        process.pid,
        shlex.join(list(command)),
    )
    capture = StderrCapture()

    def read_stderr() -> None:
        stream = process.stderr
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                try:
                    sys.stderr.write(line)
                    sys.stderr.flush()
                except Exception:
                    pass
                capture.feed(line)
        finally:
            try:
                stream.close()
            except OSError:
                pass

    reader = threading.Thread(
        target=read_stderr,
        name=f"watchdog-stderr-{process.pid}",
        daemon=True,
    )
    reader.start()
    try:
        while process.poll() is None:
            if stop_event.wait(0.25):
                _terminate_process(process, logger)
                break
        returncode = process.wait()
    finally:
        reader.join(timeout=5)
    captured = capture.result()
    return ChildResult(
        command=list(command),
        pid=process.pid,
        returncode=int(returncode),
        started_at=started,
        ended_at=time.time(),
        stderr_tail=_redact(captured["recent"]),
        traceback_text=_redact(captured["traceback"]),
    )


def _exception_details(traceback_text: str) -> Dict[str, Any]:
    frames = list(_FRAME_RE.finditer(traceback_text or ""))
    filename = frames[-1].group("file") if frames else "-"
    line_number: Any = int(frames[-1].group("line")) if frames else "-"
    error_type = "UnhandledException"
    summary = "فرایند با یک Exception مدیریت‌نشده متوقف شد"
    for raw_line in reversed((traceback_text or "").splitlines()):
        cleaned = raw_line.strip().lstrip("|+- ").strip()
        match = re.match(r"^(?P<type>[A-Za-z_][\w.]*):\s*(?P<message>.*)$", cleaned)
        if match:
            error_type = match.group("type").split(".")[-1]
            summary = match.group("message").strip() or cleaned
            break
        if cleaned in {"KeyboardInterrupt", "SystemExit"}:
            error_type = cleaned
            summary = cleaned
            break
    return {
        "error_type": error_type,
        "file": filename,
        "line": line_number,
        "summary": summary,
    }


def analyze_child_result(result: ChildResult) -> Dict[str, Any]:
    """Extract the exception class, deepest frame and diagnostic summary."""
    traceback_text = result.traceback_text or result.stderr_tail
    if result.traceback_text:
        details = _exception_details(result.traceback_text)
    elif result.returncode < 0:
        signal_number = -result.returncode
        try:
            signal_name = signal.Signals(signal_number).name
        except (ValueError, AttributeError):
            signal_name = str(signal_number)
        details = {
            "error_type": "ProcessSignalExit",
            "file": result.command[-1] if result.command else "main.py",
            "line": "-",
            "summary": f"فرایند با سیگنال {signal_name} متوقف شد",
        }
    else:
        details = {
            "error_type": "UnexpectedProcessExit",
            "file": result.command[-1] if result.command else "main.py",
            "line": "-",
            "summary": f"فرایند به‌طور غیرعادی با exit code {result.returncode} متوقف شد",
        }
    details.update({
        "time_local": now_local().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "created_at_epoch": result.ended_at,
        "exit_code": result.returncode,
        "pid": result.pid,
        "uptime_seconds": round(result.uptime_seconds, 3),
        "command": result.command,
        "traceback": traceback_text or (
            f"No Python traceback was emitted. Exit code: {result.returncode}"
        ),
    })
    fingerprint_text = "|".join(
        str(details.get(key, ""))
        for key in ("error_type", "file", "line", "summary")
    )
    details["fingerprint"] = hashlib.sha256(
        fingerprint_text.encode("utf-8", "replace")
    ).hexdigest()
    return details


def _spawn_failure_incident(command: Sequence[str], error: BaseException) -> Dict[str, Any]:
    summary = f"Watchdog نتوانست فرایند ربات را اجرا کند: {error}"
    incident = {
        "time_local": now_local().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "created_at_epoch": time.time(),
        "error_type": type(error).__name__,
        "file": command[-1] if command else "main.py",
        "line": "-",
        "summary": summary,
        "exit_code": None,
        "pid": None,
        "uptime_seconds": 0,
        "command": list(command),
        "traceback": summary,
    }
    incident["fingerprint"] = hashlib.sha256(
        "|".join(str(incident[key]) for key in (
            "error_type", "file", "line", "summary"
        )).encode("utf-8", "replace")
    ).hexdigest()
    return incident


def write_crash_log(incident: Dict[str, Any]) -> Path:
    stamp = now_local().strftime("%Y%m%d-%H%M%S-%f")
    pid = incident.get("pid") or "spawn"
    path = runtime_log_file(f"watchdog-crash-{stamp}-{pid}.log")
    command = incident.get("command") or []
    body = (
        "WATCHDOG CRASH REPORT\n"
        f"time={incident.get('time_local')}\n"
        f"type={incident.get('error_type')}\n"
        f"file={incident.get('file')}\n"
        f"line={incident.get('line')}\n"
        f"summary={incident.get('summary')}\n"
        f"exit_code={incident.get('exit_code')}\n"
        f"pid={incident.get('pid')}\n"
        f"uptime_seconds={incident.get('uptime_seconds')}\n"
        f"command={shlex.join([str(part) for part in command]) if command else '-'}\n"
        "\nFULL TRACEBACK / STDERR\n"
        "=======================\n"
        f"{incident.get('traceback') or '-'}\n"
    )
    path.write_text(body, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def _interruptible_sleep(stop_event: threading.Event, seconds: float) -> bool:
    return stop_event.wait(max(0.0, seconds))


def _fallback_owner_delivery(logger: logging.Logger) -> bool:
    if pending_count() <= 0:
        return True
    try:
        delivered = asyncio.run(deliver_with_fresh_client(
            status="نیاز به بررسی دارد",
            logger=ReporterLoggerAdapter(logger),
        ))
        logger.info("WATCHDOG FALLBACK OWNER DELIVERY delivered=%s", delivered)
        return True
    except Exception as error:
        logger.error("WATCHDOG FALLBACK OWNER DELIVERY FAILED error=%r", error)
        return False


def _parse_command(remainder: Sequence[str]) -> List[str]:
    command = list(remainder)
    if command and command[0] == "--":
        command = command[1:]
    return command or [sys.executable, "-u", "main.py"]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Permanent crash-only supervisor for the Soroush Plus bot",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="monitor one run without restarting (abnormal exit still logged)",
    )
    parser.add_argument(
        "--no-owner-report",
        action="store_true",
        help="disable owner delivery; intended only for local tests",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="optional child command after --; default: current Python -u main.py",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    # Watchdog settings live beside the bot's existing credentials/settings;
    # load them before reading restart/cooldown limits.
    load_dotenv(PROJECT_ROOT / ".env")
    args = build_argument_parser().parse_args(argv)
    command = _parse_command(args.command)
    logger = setup_logger()
    stop_event = threading.Event()

    def request_stop(signum: int, _frame: Any) -> None:
        if not stop_event.is_set():
            logger.info("WATCHDOG STOP REQUEST signal=%s", signum)
        stop_event.set()

    # run_child owns its Popen internally; signals are observed via stop_event.
    # SIGTERM/SIGINT do not create owner reports or restart the bot.
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    instance = SingleInstance(LOCK_FILE)
    try:
        instance.acquire()
    except RuntimeError as error:
        print(f"Watchdog اجرا نشد: {error}", file=sys.stderr)
        logger.error("WATCHDOG DUPLICATE INSTANCE error=%s", error)
        return 2

    base_delay = _env_float("WATCHDOG_RESTART_DELAY", 5.0)
    max_delay = _env_float("WATCHDOG_MAX_RESTART_DELAY", 60.0, base_delay)
    stable_seconds = _env_float("WATCHDOG_STABLE_SECONDS", 300.0)
    report_cooldown = _env_float("WATCHDOG_REPORT_COOLDOWN", 15 * 60)
    rapid_window = _env_float("WATCHDOG_RAPID_FAILURE_WINDOW", 20.0)
    rapid_limit = _env_int("WATCHDOG_RAPID_FAILURE_LIMIT", 3)
    consecutive_failures = 0
    rapid_failures = 0

    logger.info(
        "WATCHDOG START pid=%s command=%s restart=%s",
        os.getpid(),
        shlex.join(command),
        not args.once,
    )
    try:
        while not stop_event.is_set():
            try:
                result = run_child(command, stop_event, logger)
            except (OSError, ValueError) as error:
                if stop_event.is_set():
                    break
                incident = _spawn_failure_incident(command, error)
                crash_log = write_crash_log(incident)
                incident["crash_log"] = str(crash_log)
                logger.critical(
                    "WATCHDOG CHILD SPAWN FAILED type=%s file=%s error=%r log=%s",
                    incident["error_type"], incident["file"], error, crash_log,
                )
                if not args.no_owner_report:
                    queue_incident(
                        incident,
                        cooldown_seconds=report_cooldown,
                    )
                    _fallback_owner_delivery(logger)
                if args.once:
                    return 1
                consecutive_failures += 1
                delay = min(
                    max_delay,
                    base_delay * (2 ** min(consecutive_failures - 1, 5)),
                )
                if _interruptible_sleep(stop_event, delay):
                    break
                continue

            if stop_event.is_set():
                logger.info(
                    "WATCHDOG CHILD STOPPED BY SUPERVISOR pid=%s exit_code=%s",
                    result.pid, result.returncode,
                )
                break

            incident = analyze_child_result(result)
            crash_log = write_crash_log(incident)
            incident["crash_log"] = str(crash_log)
            logger.critical(
                "WATCHDOG CRASH pid=%s exit_code=%s uptime=%.3fs "
                "type=%s file=%s line=%s summary=%s log=%s",
                result.pid,
                result.returncode,
                result.uptime_seconds,
                incident["error_type"],
                incident["file"],
                incident["line"],
                incident["summary"],
                crash_log,
            )

            if result.uptime_seconds >= stable_seconds:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
            if result.uptime_seconds < rapid_window:
                rapid_failures += 1
            else:
                rapid_failures = 0

            if not args.no_owner_report:
                queued = queue_incident(
                    incident,
                    cooldown_seconds=report_cooldown,
                )
                logger.info(
                    "WATCHDOG OWNER REPORT QUEUED new=%s pending=%s",
                    queued, pending_count(),
                )

            if args.once:
                if not args.no_owner_report:
                    _fallback_owner_delivery(logger)
                return result.returncode if result.returncode != 0 else 1

            # A normal restart delivers the pending report from the bot's own
            # connected client.  If the bot dies repeatedly before startup is
            # complete, no child is alive here, so a temporary reporting
            # client is safe and marks the status as requiring investigation.
            if (
                not args.no_owner_report
                and rapid_failures >= rapid_limit
                and pending_count() > 0
            ):
                _fallback_owner_delivery(logger)
                rapid_failures = 0

            delay = min(
                max_delay,
                base_delay * (2 ** min(max(0, consecutive_failures - 1), 5)),
            )
            logger.info(
                "WATCHDOG RESTART SCHEDULED delay=%.1fs consecutive_failures=%s",
                delay, consecutive_failures,
            )
            if _interruptible_sleep(stop_event, delay):
                break

        return 0
    finally:
        logger.info("WATCHDOG STOP pid=%s", os.getpid())
        instance.close()


if __name__ == "__main__":
    raise SystemExit(main())
