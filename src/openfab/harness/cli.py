"""명령줄에서 조건표 하나로 실험을 실행한다.

    python -m openfab.harness configs/experiments/example.yaml
"""

from __future__ import annotations

import argparse

from openfab.harness.conditions import expand, load_experiment
from openfab.harness.runner import run_experiment


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="OpenFab 실험 하네스")
    parser.add_argument("experiment", help="실험 조건표 YAML 경로")
    parser.add_argument("--out", default="results", help="결과를 저장할 폴더 (기본: results)")
    args = parser.parse_args(argv)

    experiment = load_experiment(args.experiment)
    runs = len(expand(experiment)) * len(experiment.seeds)
    print(f"[{experiment.name}] {runs}회 실행합니다")
    folder = run_experiment(experiment, args.out)
    print(f"결과: {folder / 'results.csv'}")


if __name__ == "__main__":
    main()
