from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project_root() -> Path:
    return ROOT


@pytest.fixture
def example_config() -> Path:
    return ROOT / "configs" / "experiments" / "E001_pi-estimate.yaml"


@pytest.fixture
def smoke_overlay() -> Path:
    return ROOT / "configs" / "debug" / "smoke.yaml"


@pytest.fixture
def write_yaml(tmp_path):
    """Write a dict as YAML under tmp_path and return the path."""

    def write(name: str, data: dict) -> Path:
        path = tmp_path / name
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    return write
