"""Command line: ``expkit run -c <config> [-c <overlay> ...] [key=value ...]`` and
``expkit report <experiment>``."""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import RunSpec, experiment_name, load_config
from .report import collect_runs, find_experiment_dir, render_markdown
from .run import start_run


def find_project_root(start: Path) -> Path:
    for path in (start, *start.parents):
        if (path / "pyproject.toml").is_file():
            return path
    return Path.cwd()


def resolve_entry(entry: str) -> Callable[..., Any]:
    module_name, _, func_name = entry.partition(":")
    if not func_name:
        raise ValueError(f"run.entry must look like 'module:function', got {entry!r}")
    return getattr(importlib.import_module(module_name), func_name)


def cmd_run(args: argparse.Namespace) -> int:
    config_paths = [Path(p).resolve() for p in args.config]
    # The first file is the experiment; later ones are overlays such as configs/debug/smoke.yaml.
    experiment = experiment_name(config_paths[0])
    root = find_project_root(config_paths[0].parent)
    cfg = load_config(config_paths, args.overrides, local=root / "configs" / "local.yaml")
    # Import the entry before start_run so set_seed also seeds numpy / torch it imports.
    entry = resolve_entry(RunSpec.from_config(cfg).entry)
    with start_run(
        cfg,
        experiment=experiment,
        project_root=root,
        config_paths=config_paths,
        overrides=args.overrides,
    ) as run:
        run.finish("success", results=entry(cfg, run))
    print(run.path)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    root = find_project_root(Path.cwd())
    output_root = args.output_root
    if output_root is None:
        base = load_config(root / "configs" / "base.yaml", local=root / "configs" / "local.yaml")
        output_root = base.get("run", {}).get("output_root", "outputs")
    output_root = Path(output_root) if Path(output_root).is_absolute() else root / output_root
    exp_dir = find_experiment_dir(output_root, args.experiment)
    text = render_markdown(exp_dir.name, collect_runs(exp_dir))
    if args.save:
        target = root / "reports" / f"{exp_dir.name}_runs.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="expkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run one experiment config into a fresh output directory")
    p_run.add_argument(
        "-c",
        "--config",
        action="append",
        required=True,
        help="experiment config, e.g. configs/experiments/E001_pi-estimate.yaml; repeat to add "
        "overlays such as configs/debug/smoke.yaml (merged left to right)",
    )
    p_run.add_argument("overrides", nargs="*", help="key.sub=value; prefix + to add a new key")
    p_run.set_defaults(func=cmd_run)

    p_report = sub.add_parser("report", help="tabulate all runs of one experiment")
    p_report.add_argument("experiment", help="full name (E001_pi-estimate) or number (E001)")
    p_report.add_argument(
        "--save", action="store_true", help="also write the table to reports/<experiment>_runs.md"
    )
    p_report.add_argument("--output-root", help="defaults to run.output_root of configs/base.yaml")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
