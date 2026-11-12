"""조건 하나를 한 번 실행하고, 사건 기록과 장비 상태 타임라인을 파일로 남긴다.

    python -m openfab.harness.trace configs/factory.yaml --seed 1 \\
        --set processes.photo.machines=2 --set release.interval=15

results/trace/<이름>/ 에 다음이 생긴다.
    config.yaml    실행에 쓴 공장 설정과 seed (재현용)
    events.csv     사건 1개당 한 줄: 시각, 종류, Lot, 공정, 장비 번호
    timeline.csv   장비 상태 구간 1개당 한 줄: 공정, 장비 번호, 상태, 시작, 끝, Lot
    timeline.png   장비별 상태 띠 그래프 (처리 중 = 초록, 대기 = 회색)

결과표(results.csv)는 실행 1회를 숫자 몇 개로 줄인 요약이고, 이 파일들은 그 안에서 실제로
무슨 일이 있었는지를 보여준다. [4층] 디지털 트윈은 timeline.csv를 읽어 장비 색을 칠한다.
"""

from __future__ import annotations

import argparse
import copy
import csv
from pathlib import Path
from typing import Any

import matplotlib
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from openfab.harness.conditions import Override, build_factory  # noqa: E402
from openfab.sim import EquipmentState, SimResult, StateInterval, machine_timeline, simulate  # noqa: E402

STATE_COLORS = {EquipmentState.PROCESSING: "#2e9e5b", EquipmentState.IDLE: "#d9d9d9"}


def run_trace(
    base: dict[str, Any], seed: int, override: Override | None = None, out_dir: str | Path = "results/trace/trace"
) -> Path:
    """실행 1회의 사건·타임라인을 out_dir에 쓰고 그 경로를 돌려준다."""
    override = override or {}
    result = simulate(build_factory(base, override), seed)
    timeline = machine_timeline(result)

    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "config.yaml", "w", encoding="utf-8") as f:
        meta = {"base": copy.deepcopy(base), "override": override, "seed": seed}
        yaml.safe_dump(meta, f, allow_unicode=True, sort_keys=False)

    _write_csv(
        folder / "events.csv",
        ["time", "kind", "lot_id", "process", "machine"],
        ([round(e.time, 3), e.kind.value, e.lot_id, e.process or "", "" if e.machine is None else e.machine]
         for e in result.events),
    )
    _write_csv(
        folder / "timeline.csv",
        ["process", "machine", "state", "start", "end", "lot_id"],
        ([i.process, i.machine, i.state.value, round(i.start, 3), round(i.end, 3), i.lot_id or ""] for i in timeline),
    )
    plot_timeline(result, timeline, folder / "timeline.png")
    return folder


def plot_timeline(result: SimResult, timeline: list[StateInterval], out: str | Path) -> Path:
    """장비 한 대가 한 줄인 띠 그래프. 위에서 아래로 공정 순서."""
    machines = [(name, m) for name, stats in result.processes.items() for m in range(stats.machines)]
    fig, ax = plt.subplots(figsize=(10, 0.4 * len(machines) + 1.2))
    for row, key in enumerate(machines):
        for state, color in STATE_COLORS.items():
            bars = [(i.start, i.duration) for i in timeline if (i.process, i.machine) == key and i.state is state]
            ax.broken_barh(bars, (row - 0.4, 0.8), facecolors=color)
    ax.set_yticks(range(len(machines)), [f"{name} #{m}" for name, m in machines])
    ax.invert_yaxis()
    ax.set_xlim(0, result.makespan)
    ax.set_xlabel("time (min)")  # 기본 폰트에 한글이 없어 영문으로 표기
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in STATE_COLORS.values()]
    ax.legend(handles, [s.value for s in STATE_COLORS], loc="upper right", ncols=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return Path(out)


def parse_overrides(items: list[str]) -> Override:
    override: Override = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key or not value:
            raise ValueError(f"--set은 '키=값' 형식입니다: {item!r}")
        override[key] = yaml.safe_load(value)  # "2" → 2, "exponential" → 글자 그대로
    return override


def _write_csv(path: Path, header: list[str], rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="OpenFab 실행 1회의 사건·장비 상태 기록")
    parser.add_argument("factory", help="공장 설정 YAML 경로")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--set", action="append", default=[], metavar="키=값", help="바꿀 값 (조건표의 vary 키와 같음)")
    parser.add_argument("--name", default="trace", help="결과 폴더 이름")
    parser.add_argument("--out", default="results/trace", help="결과를 저장할 상위 폴더")
    args = parser.parse_args(argv)

    with open(args.factory, encoding="utf-8") as f:
        base = yaml.safe_load(f)
    folder = run_trace(base, args.seed, parse_overrides(args.set), Path(args.out) / args.name)
    print(f"결과: {folder}")


if __name__ == "__main__":
    main()
