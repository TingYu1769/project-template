"""Every experiment config must keep resolving; catches broken ``extends`` and entry points."""

from __future__ import annotations

from pathlib import Path

import pytest

from expkit.cli import resolve_entry
from expkit.config import RunSpec, experiment_name, load_config

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = sorted((ROOT / "configs" / "experiments").glob("*.yaml"))
OVERLAYS = sorted((ROOT / "configs" / "debug").glob("*.yaml"))


def test_there_is_at_least_one_experiment():
    assert EXPERIMENTS


@pytest.mark.parametrize("path", EXPERIMENTS, ids=lambda p: p.stem)
def test_experiment_is_named_by_convention_and_its_entry_exists(path):
    experiment_name(path)
    spec = RunSpec.from_config(load_config(path))
    assert callable(resolve_entry(spec.entry))


@pytest.mark.parametrize("overlay", OVERLAYS, ids=lambda p: p.stem)
@pytest.mark.parametrize("path", EXPERIMENTS, ids=lambda p: p.stem)
def test_debug_overlay_applies_to_every_experiment(path, overlay):
    spec = RunSpec.from_config(load_config([path, overlay]))
    assert spec.debug is True
