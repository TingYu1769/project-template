"""Example experiment entry point: Monte Carlo estimate of pi. Replace with your own.

An entry point has the signature ``(cfg, run) -> dict``: it gets the resolved config and
the ``Run`` handle, logs progress through ``run``, and returns the final metrics, which
the CLI writes to ``results.json``. Configs select it with ``run.entry: module:function``.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any

from .run import Run

log = logging.getLogger(__name__)


def estimate_pi(cfg: dict[str, Any], run: Run) -> dict[str, Any]:
    task = cfg["task"]
    rng = random.Random(run.spec.seed)
    inside = total = 0
    for batch in range(task["n_batches"]):
        hits = sum(rng.random() ** 2 + rng.random() ** 2 <= 1.0 for _ in range(task["batch_size"]))
        inside += hits
        total += task["batch_size"]
        run.log_sample({"batch": batch, "hits": hits, "n": task["batch_size"]})
        run.log_metrics(step=batch, n=total, estimate=4 * inside / total)
    estimate = 4 * inside / total
    log.info("pi estimate %.5f from %d samples", estimate, total)
    return {"estimate": estimate, "abs_error": abs(estimate - math.pi), "n_samples": total}
