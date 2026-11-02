"""조건표의 모든 조합 × seed를 실행하고 결과표(CSV)를 남긴다."""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from openfab.harness.conditions import Experiment, build_factory, expand
from openfab.sim import simulate


def run_experiment(experiment: Experiment, out_dir: str | Path = "results") -> Path:
    """실험을 실행하고 결과 폴더 경로를 돌려준다.

    results/<name>/experiment.yaml  실행에 쓴 조건표 사본 (재현용)
    results/<name>/results.csv      실행 1회당 한 줄
    """
    folder = Path(out_dir) / experiment.name
    folder.mkdir(parents=True, exist_ok=True)

    with open(folder / "experiment.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(experiment.to_dict(), f, allow_unicode=True, sort_keys=False)

    rows = []
    for run_index, override in enumerate(expand(experiment)):
        factory = build_factory(experiment.base, override)
        for seed in experiment.seeds:
            result = simulate(factory, seed)
            rows.append({"run": run_index, **override, **result.summary()})

    with open(folder / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return folder
