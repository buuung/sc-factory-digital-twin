"""결과표를 그래프로 그린다. 같은 조건의 여러 seed는 평균을 낸다."""

from __future__ import annotations

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
) -> Path:
    """x축 조건에 따른 y 지표의 평균을 그린다. group_by를 주면 값마다 선을 하나씩 그린다."""
    with open(results_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for column in filter(None, (x, y, group_by)):
        if column not in rows[0]:
            raise KeyError(f"결과표에 없는 열입니다: {column} (있는 열: {list(rows[0])})")

    lines: dict[str, dict[float, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        label = f"{group_by}={row[group_by]}" if group_by else y
        lines[label][float(row[x])].append(float(row[y]))

    fig, ax = plt.subplots(figsize=(6, 4))
    for label, points in lines.items():
        xs = sorted(points)
        ax.plot(xs, [sum(points[v]) / len(points[v]) for v in xs], marker="o", label=label)
    ax.set_xlabel(x)
    ax.set_ylabel(f"{y} (mean over seeds)")  # 기본 폰트에 한글이 없어 영문으로 표기
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()

    out_path = Path(out) if out else Path(results_csv).with_name(f"{y}_by_{x}.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
