from __future__ import annotations

import json
import re

import pytest

from expkit.config import load_config
from expkit.run import start_run

EXPERIMENT = "E001_pi-estimate"


def _cfg(example_config, tmp_path, *overrides):
    return load_config(example_config, [f"run.output_root={tmp_path}", *overrides])


def _manifest(run):
    return json.loads((run.path / "manifest.json").read_text(encoding="utf-8"))


def test_run_dir_sits_under_experiment_name_and_carries_label(
    example_config, project_root, tmp_path
):
    cfg = _cfg(example_config, tmp_path, "run.label=seed1")
    with start_run(cfg, experiment=EXPERIMENT, project_root=project_root) as run:
        pass
    assert run.path.parent == tmp_path / EXPERIMENT
    assert re.fullmatch(r"\d{8}-\d{6}_seed1_[0-9a-f]{4}", run.path.name), run.path.name
    assert _manifest(run)["label"] == "seed1"


def test_run_dir_without_label_has_only_timestamp_and_suffix(
    example_config, project_root, tmp_path
):
    with start_run(
        _cfg(example_config, tmp_path), experiment=EXPERIMENT, project_root=project_root
    ) as run:
        pass
    assert re.fullmatch(r"\d{8}-\d{6}_[0-9a-f]{4}", run.path.name), run.path.name


def test_runs_never_share_a_directory(example_config, project_root, tmp_path):
    paths = set()
    for _ in range(2):
        with start_run(
            _cfg(example_config, tmp_path), experiment=EXPERIMENT, project_root=project_root
        ) as run:
            paths.add(run.path)
    assert len(paths) == 2


def test_debug_runs_go_under_debug_dir(example_config, smoke_overlay, project_root, tmp_path):
    cfg = load_config([example_config, smoke_overlay], [f"run.output_root={tmp_path}"])
    with start_run(cfg, experiment=EXPERIMENT, project_root=project_root) as run:
        pass
    assert run.path.parent == tmp_path / "_debug" / EXPERIMENT
    assert _manifest(run)["debug"] is True


def test_exception_marks_run_failed_and_keeps_traceback(example_config, project_root, tmp_path):
    cfg = _cfg(example_config, tmp_path)
    with (
        pytest.raises(RuntimeError),
        start_run(cfg, experiment=EXPERIMENT, project_root=project_root) as run,
    ):
        raise RuntimeError("boom")
    manifest = _manifest(run)
    assert manifest["status"] == "failed"
    assert "boom" in manifest["error"]


def test_ctrl_c_marks_run_interrupted(example_config, project_root, tmp_path):
    cfg = _cfg(example_config, tmp_path)
    with (
        pytest.raises(KeyboardInterrupt),
        start_run(cfg, experiment=EXPERIMENT, project_root=project_root) as run,
    ):
        raise KeyboardInterrupt
    assert _manifest(run)["status"] == "interrupted"


@pytest.mark.parametrize("label", ["seed_1", "Seed1", "-x", ""])
def test_label_outside_naming_rule_is_rejected(label, example_config, project_root, tmp_path):
    cfg = _cfg(example_config, tmp_path, f"run.label='{label}'")
    with pytest.raises(ValueError, match="run.label"):
        start_run(cfg, experiment=EXPERIMENT, project_root=project_root)
