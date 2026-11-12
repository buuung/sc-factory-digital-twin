"""조건표의 모든 조합 × seed를 실행하고 결과표(CSV)를 남긴다."""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from openfab.harness.conditions import Experiment, build_factory, expand
from openfab import theory
from openfab.sim import FactoryConfig, simulate


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
            rows.append({"run": run_index, **override, **result.summary(), "limited_by": limited_by(factory)})

    with open(folder / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return folder


def limited_by(factory: FactoryConfig) -> str:
    """생산량의 상한을 정하는 것: 투입이 모자라면 "release", 넘치면 처리능력이 가장 작은 공정.

    결과표의 bottleneck 열은 "가동률이 가장 높은 공정"이라 투입이 모자라 대기가 없을 때도
    공정 이름이 찍힌다. 이 열은 측정값이 아니라 설정(투입률과 공정 처리능력)에서 계산한 값이며,
    장비를 늘려서 생산량이 늘 수 있는 상황인지 구분하는 데 쓴다.
    """
    interval = factory.release.interval
    if interval > 0 and 1 / interval < theory.max_throughput(factory):
        return "release"
    return theory.bottleneck(factory)
