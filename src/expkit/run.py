"""Per-run output directories: resolved config, manifest, atomic JSON and append-only JSONL.

Every run gets a fresh directory that is never reused:
``<output_root>/<experiment>/<YYYYMMDD-HHMMSS>[_<label>]_<4 hex>/``, e.g.
``outputs/E001_pi-estimate/20261026-153012_seed1_a3f9/``. Debug runs (``run.debug: true``,
set by ``configs/debug/*.yaml``) go under ``<output_root>/_debug/`` instead, so they never
mix with real results. In names, ``_`` separates fields and ``-`` joins words.
``manifest.json`` records what is needed to reproduce the run: git commit and dirty state (the diff itself goes to ``git.diff``), argv, overrides, seed, host,
Python, the uv.lock hash, timing and final status.

JSON files are written to a temp file and atomically replaced; JSONL lines are fsynced on append,
so a killed process never leaves a half-written record.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import random
import re
import secrets
import socket
import subprocess
import sys
import traceback
import warnings
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import yaml

from .config import EXPERIMENT_NAME, RunSpec

SCHEMA_VERSION = 1
LABEL = re.compile(r"[a-z0-9][a-z0-9.-]*")  # no "_": it separates the fields of a run id

log = logging.getLogger(__name__)


def digest(value: Any) -> str:
    data = (
        value
        if isinstance(value, bytes)
        else json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    )
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> None:
    """Write JSON atomically: after a crash the file is either the old or the new version."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".pending")
    with pending.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    pending.replace(path)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _cmd(args: list[str], cwd: Path) -> str | None:
    try:
        out = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def git_state(root: Path) -> tuple[dict[str, Any], str]:
    """Return (git fields for the manifest, ``git diff HEAD`` text). Fields are None outside git."""
    commit = _cmd(["git", "rev-parse", "HEAD"], root)
    if commit is None:
        warnings.warn(
            f"{root} is not a git repository with at least one commit; git fields will be null",
            stacklevel=3,
        )
        return {"commit": None, "branch": None, "dirty": None, "untracked": None}, ""
    status = _cmd(["git", "status", "--porcelain"], root) or ""
    diff = _cmd(["git", "diff", "HEAD", "--binary"], root) or ""
    branch = (_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], root) or "").strip()
    return {
        "commit": commit.strip(),
        "branch": branch or None,
        "dirty": bool(status.strip()),
        # Untracked files are not in git.diff; list them so a dirty run is still explainable.
        "untracked": [line[3:] for line in status.splitlines() if line.startswith("??")],
    }, diff


def env_state(root: Path) -> dict[str, Any]:
    lock = root / "uv.lock"
    gpus = _cmd(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], root)
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "host": socket.gethostname(),
        "uv_lock_sha256": digest(lock.read_bytes()) if lock.is_file() else None,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "gpus": gpus.strip().splitlines() if gpus else [],
    }


def set_seed(seed: int) -> None:
    """Seed Python's global RNG, and numpy / torch if the experiment has already imported them."""
    random.seed(seed)
    if "numpy" in sys.modules:
        sys.modules["numpy"].random.seed(seed)
    if "torch" in sys.modules:
        sys.modules["torch"].manual_seed(seed)


class Run:
    """Handle to one run directory. Created by ``start_run``; use it as a context manager.

    Leaving the ``with`` block normally marks the run ``success``; an exception marks it
    ``failed`` (``interrupted`` for Ctrl-C) and stores the traceback in the manifest.
    """

    def __init__(self, path: Path, spec: RunSpec, manifest: dict[str, Any]):
        self.path = path
        self.spec = spec
        self.manifest = manifest
        self._log_handler: logging.Handler | None = None

    @property
    def artifacts(self) -> Path:
        """Directory for large files: checkpoints, videos, generated data."""
        path = self.path / "artifacts"
        path.mkdir(exist_ok=True)
        return path

    def log_metrics(self, step: int, **values: Any) -> None:
        append_jsonl(self.path / "metrics.jsonl", {"step": step, "time": _now(), **values})

    def log_sample(self, record: dict[str, Any]) -> None:
        """One line per sample / episode / trajectory in ``samples.jsonl``."""
        append_jsonl(self.path / "samples.jsonl", record)

    def finish(
        self,
        status: str = "success",
        results: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if results is not None:
            write_json(self.path / "results.json", results)
        ended = datetime.now().astimezone()
        started = datetime.fromisoformat(self.manifest["started_at"])
        self.manifest.update(
            status=status,
            ended_at=ended.isoformat(),
            duration_s=round((ended - started).total_seconds(), 3),
            error=error,
        )
        write_json(self.path / "manifest.json", self.manifest)
        log.info("run %s: %s", status, self.path)
        self._close_log()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self.manifest["status"] != "running":
            return
        if exc_type is None:
            self.finish("success")
        else:
            status = "interrupted" if issubclass(exc_type, KeyboardInterrupt) else "failed"
            self.finish(status, error="".join(traceback.format_exception(exc_type, exc, tb)))

    def _open_log(self) -> None:
        handler = logging.FileHandler(self.path / "run.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger()
        if root.level > logging.INFO:
            root.setLevel(logging.INFO)
        root.addHandler(handler)
        self._log_handler = handler

    def _close_log(self) -> None:
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler.close()
            self._log_handler = None


def start_run(
    cfg: dict[str, Any],
    *,
    experiment: str,
    project_root: Path,
    config_paths: Sequence[str | Path] = (),
    overrides: Sequence[str] = (),
) -> Run:
    """Create a new run directory, write config.yaml / manifest.json / git.diff, seed RNGs."""
    spec = RunSpec.from_config(cfg)
    if not EXPERIMENT_NAME.fullmatch(experiment):
        raise ValueError(f"experiment {experiment!r} must match {EXPERIMENT_NAME.pattern}")
    if spec.label is not None and not LABEL.fullmatch(spec.label):
        raise ValueError(f"run.label={spec.label!r} must match {LABEL.pattern}")

    project_root = project_root.resolve()
    output_root = Path(spec.output_root)
    if not output_root.is_absolute():
        output_root = project_root / output_root
    if spec.debug:
        output_root = output_root / "_debug"
    started_at = _now()
    stamp = datetime.fromisoformat(started_at).strftime("%Y%m%d-%H%M%S")
    run_id = "_".join(part for part in (stamp, spec.label, secrets.token_hex(2)) if part)
    path = output_root / experiment / run_id
    path.mkdir(parents=True, exist_ok=False)  # never write into an existing run

    git, diff = git_state(project_root)
    if diff:
        (path / "git.diff").write_text(diff, encoding="utf-8")
    git["diff_file"] = "git.diff" if diff else None
    (path / "config.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "experiment": experiment,
        "exp_id": experiment.split("_", 1)[0],
        "label": spec.label,
        "debug": spec.debug,
        "seed": spec.seed,
        "entry": spec.entry,
        "status": "running",
        "started_at": started_at,
        "ended_at": None,
        "duration_s": None,
        "argv": sys.argv,
        "cwd": os.getcwd(),
        "config_paths": [_relative_to(Path(p), project_root) for p in config_paths],
        "overrides": list(overrides),
        "config_sha256": digest(cfg),
        "git": git,
        "env": env_state(project_root),
        "error": None,
    }
    write_json(path / "manifest.json", manifest)

    run = Run(path, spec, manifest)
    run._open_log()
    set_seed(spec.seed)
    log.info("run started: %s", path)
    return run


def _relative_to(path: Path, root: Path) -> str:
    path = path.resolve()
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
