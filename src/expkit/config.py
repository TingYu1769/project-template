"""YAML config loading with ``extends`` inheritance and dotted command-line overrides.

A config file may declare ``extends: base.yaml`` (or a list of files), resolved
relative to the file itself. Parents are merged first, then the child on top.

Several files can be given; they are merged left to right, so a debug overlay such as
``configs/debug/smoke.yaml`` can be layered on top of any experiment.

Overrides use ``key.sub=value``; the value is parsed as YAML, so ``1`` is an int,
``true`` a bool and ``[1, 2]`` a list. Overriding a key that does not exist is
an error (it is usually a typo); prefix it with ``+`` to add a new key on purpose.

An experiment is named by its config file, ``E<3 digits>_<words-joined-by-dashes>.yaml``
(e.g. ``E001_pi-estimate.yaml``): the number identifies it, the words tell people what
it is. The YAML does not repeat the name.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml

EXPERIMENT_NAME = re.compile(r"E\d{3}_[a-z0-9]+(?:-[a-z0-9]+)*")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise TypeError(f"{path}: top level must be a mapping, got {type(data).__name__}")
    return data


def _load_with_extends(path: Path, chain: tuple[Path, ...] = ()) -> dict[str, Any]:
    if path in chain:
        cycle = " -> ".join(str(p) for p in (*chain, path))
        raise ValueError(f"circular extends: {cycle}")
    raw = _read_yaml(path)
    parents = raw.pop("extends", None)
    if parents is None:
        return raw
    if isinstance(parents, str):
        parents = [parents]
    merged: dict[str, Any] = {}
    for parent in parents:
        parent_path = (path.parent / parent).resolve()
        merged = deep_merge(merged, _load_with_extends(parent_path, (*chain, path)))
    return deep_merge(merged, raw)


def parse_override(item: str) -> tuple[str, Any, bool]:
    """Split ``[+]key.sub=value`` into (key, parsed value, allow_new)."""
    if "=" not in item:
        raise ValueError(f"override must look like key=value, got {item!r}")
    key, raw_value = item.split("=", 1)
    key = key.strip()
    allow_new = key.startswith("+")
    return key.lstrip("+"), yaml.safe_load(raw_value), allow_new


def set_dotted(cfg: dict[str, Any], key: str, value: Any, allow_new: bool = False) -> None:
    node = cfg
    parts = key.split(".")
    for i, part in enumerate(parts[:-1]):
        if part not in node:
            if not allow_new:
                raise KeyError(
                    f"unknown config key {'.'.join(parts[: i + 1])!r} (use +{key}=... to add)"
                )
            node[part] = {}
        node = node[part]
        if not isinstance(node, dict):
            raise KeyError(f"{'.'.join(parts[: i + 1])!r} is not a mapping")
    if parts[-1] not in node and not allow_new:
        raise KeyError(f"unknown config key {key!r} (use +{key}=... to add)")
    node[parts[-1]] = value


def experiment_name(config_path: str | Path) -> str:
    """Return the experiment name, i.e. the config file name without ``.yaml``."""
    path = Path(config_path)
    if not EXPERIMENT_NAME.fullmatch(path.stem):
        raise ValueError(
            f"{path.name}: experiment configs must be named like E001_short-name.yaml "
            "(E + 3 digits, underscore, lowercase words joined by dashes)"
        )
    return path.stem


def load_config(
    paths: str | Path | Sequence[str | Path],
    overrides: Iterable[str] = (),
    local: str | Path | None = None,
) -> dict[str, Any]:
    """Merge ``paths`` left to right (each with its ``extends`` chain), then ``local``
    (if it exists), then the command-line overrides."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    cfg: dict[str, Any] = {}
    for path in paths:
        cfg = deep_merge(cfg, _load_with_extends(Path(path).resolve()))
    if local is not None and Path(local).is_file():
        cfg = deep_merge(cfg, _read_yaml(Path(local)))
    for item in overrides:
        key, value, allow_new = parse_override(item)
        set_dotted(cfg, key, value, allow_new)
    return cfg


@dataclass(frozen=True)
class RunSpec:
    """The ``run:`` section every experiment config must provide."""

    entry: str
    seed: int = 0
    label: str | None = None
    debug: bool = False
    output_root: str = "outputs"

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> RunSpec:
        section = cfg.get("run")
        if not isinstance(section, dict):
            raise KeyError("config is missing the 'run:' section")
        known = {f.name for f in fields(cls)}
        unknown = set(section) - known
        if unknown:
            raise KeyError(f"unknown keys in 'run:': {sorted(unknown)}")
        return cls(**section)
