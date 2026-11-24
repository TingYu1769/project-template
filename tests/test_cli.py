from __future__ import annotations

import json

import yaml

from expkit.cli import main
from expkit.run import read_jsonl


def test_run_writes_a_complete_run_directory(example_config, tmp_path, capsys):
    override = f"run.output_root={tmp_path}"
    assert main(["run", "-c", str(example_config), override, "task.n_batches=4"]) == 0

    (run_dir,) = (tmp_path / "E001_pi-estimate").iterdir()
    assert capsys.readouterr().out.strip() == str(run_dir)
    for name in ["config.yaml", "manifest.json", "results.json", "metrics.jsonl", "run.log"]:
        assert (run_dir / name).is_file(), name

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert manifest["experiment"] == "E001_pi-estimate"
    assert manifest["exp_id"] == "E001"
    assert manifest["config_paths"] == ["configs/experiments/E001_pi-estimate.yaml"]
    assert manifest["overrides"] == [override, "task.n_batches=4"]

    saved = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    assert saved["task"]["n_batches"] == 4
    assert len(read_jsonl(run_dir / "metrics.jsonl")) == 4


def test_smoke_overlay_is_recorded_after_the_experiment_config(
    example_config, smoke_overlay, tmp_path
):
    main(
        ["run", "-c", str(example_config), "-c", str(smoke_overlay), f"run.output_root={tmp_path}"]
    )
    (run_dir,) = (tmp_path / "_debug" / "E001_pi-estimate").iterdir()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config_paths"] == [
        "configs/experiments/E001_pi-estimate.yaml",
        "configs/debug/smoke.yaml",
    ]
