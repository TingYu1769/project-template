from __future__ import annotations

import pytest

from expkit.config import RunSpec, experiment_name, load_config


def test_child_overrides_parent_and_command_line_overrides_both(write_yaml):
    write_yaml("base.yaml", {"a": {"x": 1, "y": 2}, "b": 1})
    child = write_yaml("child.yaml", {"extends": "base.yaml", "a": {"y": 3}})
    assert load_config(child, ["a.x=10"]) == {"a": {"x": 10, "y": 3}, "b": 1}


def test_later_config_files_override_earlier_ones(write_yaml):
    experiment = write_yaml("exp.yaml", {"run": {"debug": False}, "task": {"n": 100, "k": 1}})
    overlay = write_yaml("overlay.yaml", {"run": {"debug": True}, "task": {"n": 3}})
    cfg = load_config([experiment, overlay])
    assert cfg == {"run": {"debug": True}, "task": {"n": 3, "k": 1}}


def test_override_of_unknown_key_is_rejected(write_yaml):
    path = write_yaml("c.yaml", {"a": 1})
    with pytest.raises(KeyError, match="unknown config key 'aa'"):
        load_config(path, ["aa=2"])


def test_plus_prefix_adds_a_new_key(write_yaml):
    path = write_yaml("c.yaml", {"a": 1})
    assert load_config(path, ["+c.d=true"]) == {"a": 1, "c": {"d": True}}


def test_circular_extends_is_rejected(write_yaml):
    write_yaml("a.yaml", {"extends": "b.yaml"})
    b = write_yaml("b.yaml", {"extends": "a.yaml"})
    with pytest.raises(ValueError, match="circular extends"):
        load_config(b)


def test_unknown_key_in_run_section_is_rejected():
    with pytest.raises(KeyError, match="slug"):
        RunSpec.from_config({"run": {"entry": "m:f", "slug": "old-style"}})


def test_experiment_name_is_the_config_file_name():
    assert experiment_name("configs/experiments/E019_timestamp-ablation.yaml") == (
        "E019_timestamp-ablation"
    )


@pytest.mark.parametrize(
    "file_name",
    [
        "E19_timestamp-ablation.yaml",
        "E019-timestamp-ablation.yaml",
        "E019_timestamp_ablation.yaml",
        "E019_Timestamp-Ablation.yaml",
        "E019.yaml",
        "smoke.yaml",
    ],
)
def test_badly_named_experiment_file_is_rejected(file_name):
    with pytest.raises(ValueError, match="E001_short-name.yaml"):
        experiment_name(file_name)
