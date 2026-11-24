from __future__ import annotations

import pytest

from expkit.cli import main
from expkit.report import collect_runs, find_experiment_dir, render_markdown


def _run(example_config, tmp_path, *overrides):
    assert main(["run", "-c", str(example_config), f"run.output_root={tmp_path}", *overrides]) == 0


def test_report_has_one_row_per_run_with_status_and_results(example_config, tmp_path):
    for seed in (0, 1):
        _run(example_config, tmp_path, f"run.seed={seed}", "task.n_batches=2")
    exp_dir = find_experiment_dir(tmp_path, "E001_pi-estimate")
    text = render_markdown(exp_dir.name, collect_runs(exp_dir))
    rows = [line for line in text.splitlines() if line.startswith("| 2")]
    assert len(rows) == 2
    assert all("| success |" in row for row in rows)
    assert "estimate" in text.splitlines()[4]


def test_experiment_is_found_by_its_number_alone(tmp_path):
    (tmp_path / "E001_pi-estimate").mkdir()
    (tmp_path / "E002_more-samples").mkdir()
    assert find_experiment_dir(tmp_path, "E002") == tmp_path / "E002_more-samples"


def test_number_shared_by_two_names_is_reported_as_ambiguous(tmp_path):
    (tmp_path / "E001_pi-estimate").mkdir()
    (tmp_path / "E001_renamed").mkdir()
    with pytest.raises(ValueError, match="several experiments"):
        find_experiment_dir(tmp_path, "E001")


def test_debug_runs_never_appear_in_report(example_config, smoke_overlay, tmp_path):
    assert (
        main(
            [
                "run",
                "-c",
                str(example_config),
                "-c",
                str(smoke_overlay),
                f"run.output_root={tmp_path}",
            ]
        )
        == 0
    )
    with pytest.raises(FileNotFoundError):
        find_experiment_dir(tmp_path, "E001")
