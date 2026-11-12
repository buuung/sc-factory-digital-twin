"""결과표를 그래프로 그린다. 같은 조건의 여러 seed는 평균을 낸다.

    python -m openfab.harness.plot results/<실험>/results.csv \\
        --x processes.photo.machines --y throughput_per_hour \\
        --group-by processes.inspection.machines --where release.interval=15
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def plot_results(
    results_csv: str | Path,
    x: str,
    y: str,
    group_by: str | None = None,
    out: str | Path | None = None,
    where: dict[str, object] | None = None,
) -> Path:
    """x축 조건에 따른 y 지표의 평균을 그린다.

    group_by  값마다 선을 하나씩 그린다
    where     조건 고정. 예: {"release.interval": 15}면 투입 간격 15분인 줄만 쓴다.
              바꾼 값이 3개 이상인 실험에서 나머지 조건이 섞여 평균 나는 것을 막는다
    """
    where = where or {}
    with open(results_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"결과표가 비어 있습니다: {results_csv}")
    for column in filter(None, (x, y, group_by, *where)):
        if column not in rows[0]:
            raise KeyError(f"결과표에 없는 열입니다: {column} (있는 열: {list(rows[0])})")

    rows = [row for row in rows if all(_same(row[k], v) for k, v in where.items())]
    if not rows:
        raise ValueError(f"where 조건에 맞는 줄이 없습니다: {where}")

    lines: dict[str, dict[float | str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        label = f"{group_by}={row[group_by]}" if group_by else y
        lines[label][_number(row[x])].append(float(row[y]))

    fig, ax = plt.subplots(figsize=(6, 4))
    for label, points in lines.items():
        xs = sorted(points, key=lambda v: (isinstance(v, str), v))
        ax.plot(xs, [sum(points[v]) / len(points[v]) for v in xs], marker="o", label=label)
    ax.set_xlabel(x)
    ax.set_ylabel(f"{y} (mean over seeds)")  # 기본 폰트에 한글이 없어 영문으로 표기
    if where:
        ax.set_title(", ".join(f"{k}={v}" for k, v in where.items()), fontsize=9)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()

    if out:
        out_path = Path(out)
    else:
        suffix = "".join(f"_{k}={v}" for k, v in where.items())
        out_path = Path(results_csv).with_name(f"{y}_by_{x}{suffix}.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def _number(text: str) -> float | str:
    """숫자면 숫자로, 아니면(예: randomness.arrival=exponential) 글자 그대로 x축에 쓴다."""
    try:
        return float(text)
    except ValueError:
        return text


def _same(cell: str, wanted: object) -> bool:
    """CSV의 "15"와 조건의 15, 15.0, "15"를 같은 값으로 본다."""
    a, b = _number(cell), _number(str(wanted))
    return a == b


def parse_where(items: list[str]) -> dict[str, str]:
    where = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key or not value:
            raise ValueError(f"--where는 '열=값' 형식입니다: {item!r}")
        where[key] = value
    return where


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="OpenFab 결과표 그래프")
    parser.add_argument("results_csv", help="results.csv 경로")
    parser.add_argument("--x", required=True, help="x축 열 (조건표에서 바꾼 값)")
    parser.add_argument("--y", required=True, help="y축 지표 열 (예: throughput_per_hour)")
    parser.add_argument("--group-by", help="값마다 선을 나눌 열")
    parser.add_argument("--where", action="append", default=[], metavar="열=값", help="조건 고정 (여러 번 가능)")
    parser.add_argument("--out", help="저장할 PNG 경로 (기본: CSV와 같은 폴더)")
    args = parser.parse_args(argv)
    print(plot_results(args.results_csv, args.x, args.y, args.group_by, args.out, parse_where(args.where)))


if __name__ == "__main__":
    main()
