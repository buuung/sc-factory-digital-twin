"""Agent가 누를 수 있는 버튼 3개: run_experiment / search_results / plot.

모든 호출은 results/agent_log.jsonl에 기록하고, 실험 실행 전에는 사람의 승인을 받는다.
"""

from __future__ import annotations

import csv
import json
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from openfab.harness.conditions import VARY_KEYS, expand, experiment_from_dict
from openfab.harness.plot import plot_results
from openfab.harness.runner import run_experiment

MAX_RUNS = 200  # Agent가 한 번에 요청할 수 있는 실행 횟수 상한

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "run_experiment",
        "description": (
            "기준 공장 설정에서 일부 값을 바꿔가며 시뮬레이션을 반복 실행한다. "
            f"vary의 키는 {', '.join(VARY_KEYS)} 중 하나다. "
            "randomness 값은 fixed 또는 exponential이다. vary의 모든 조합 × seed만큼 실행하고, "
            "조건별 seed 평균을 돌려준다. 실행 전 사람이 승인해야 하며 거절될 수 있다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "실험 이름 (영문, 밑줄)"},
                "vary": {
                    "type": "object",
                    "additionalProperties": {"type": "array"},
                    "description": '예: {"processes.photo.machines": [1, 2, 3]}',
                },
                "seeds": {"type": "array", "items": {"type": "integer"}},
                "reason": {"type": "string", "description": "이 실험을 하는 이유"},
            },
            "required": ["name", "vary", "reason"],
        },
    },
    {
        "name": "search_results",
        "description": (
            "지난 실험 결과를 찾는다. 조건별 seed 평균 지표를 돌려준다. "
            "bottleneck은 가동률이 가장 높은 공정, limited_by는 생산량 상한을 정하는 것"
            "(release면 투입이 모자란 상태)이다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "실험 이름이나 바꾼 값의 키 일부"}},
            "required": ["query"],
        },
    },
    {
        "name": "plot",
        "description": "지난 실험 결과로 그래프를 그리고 파일 경로를 돌려준다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "실험 이름"},
                "x": {"type": "string", "description": "x축 열 이름 (바꾼 값의 키)"},
                "y": {"type": "string", "description": "y축 지표 열 이름 (예: throughput_per_hour)"},
                "group_by": {"type": "string", "description": "값마다 선을 나눌 열"},
                "where": {
                    "type": "object",
                    "description": '조건 고정. 예: {"release.interval": 15}면 그 조건의 결과만 그린다',
                },
            },
            "required": ["name", "x", "y"],
        },
    },
]


def ask_human(prompt: str) -> bool:
    return input(f"{prompt}\n실행할까요? [y/N] ").strip().lower() == "y"


class Toolbox:
    def __init__(
        self,
        base_config: str | Path = "configs/factory.yaml",
        results_dir: str | Path = "results",
        approve: Callable[[str], bool] = ask_human,
    ) -> None:
        with open(base_config, encoding="utf-8") as f:
            self.base = yaml.safe_load(f)
        self.results_dir = Path(results_dir)
        self.approve = approve

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Agent의 도구 호출을 실행하고 기록한다. 오류도 Agent가 읽을 수 있게 결과로 돌려준다."""
        handlers = {"run_experiment": self.run_experiment, "search_results": self.search_results, "plot": self.plot}
        try:
            if name not in handlers:
                raise ValueError(f"없는 도구입니다: {name}")
            result = handlers[name](**arguments)
        except Exception as e:  # noqa: BLE001 - 어떤 오류든 Agent에게 그대로 알려준다
            result = {"error": f"{type(e).__name__}: {e}"}
        self._log(name, arguments, result)
        return result

    def run_experiment(
        self, name: str, vary: dict[str, list[Any]], reason: str, seeds: list[int] | None = None
    ) -> dict[str, Any]:
        experiment = experiment_from_dict({"name": name, "base": self.base, "seeds": seeds or [1, 2, 3], "vary": vary})
        runs = len(expand(experiment)) * len(experiment.seeds)
        if runs > MAX_RUNS:
            return {"error": f"실행 횟수 {runs}회가 상한 {MAX_RUNS}회를 넘습니다. 조건을 줄여 주세요."}

        plan = f"[Agent 실험 요청] {name}\n  이유: {reason}\n  바꿀 값: {vary}\n  seed: {experiment.seeds} → 총 {runs}회"
        if not self.approve(plan):
            return {"status": "rejected", "message": "사람이 실행을 거절했습니다."}

        run_experiment(experiment, self.results_dir)
        return {"status": "done", "runs": runs, **self.search_results(name)}

    def search_results(self, query: str) -> dict[str, Any]:
        found = []
        for meta_path in sorted(self.results_dir.glob("*/experiment.yaml")):
            if not meta_path.with_name("results.csv").exists():
                continue  # 실행 도중 끊긴 실험
            with open(meta_path, encoding="utf-8") as f:
                meta = yaml.safe_load(f)
            if query in meta["name"] or any(query in key for key in meta["vary"]):
                found.append(_summarize(meta, meta_path.with_name("results.csv")))
        if not found:
            return {"experiments": [], "message": f"'{query}'에 해당하는 실험 결과가 없습니다."}
        return {"experiments": found}

    def plot(
        self, name: str, x: str, y: str, group_by: str | None = None, where: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        results_csv = self.results_dir / name / "results.csv"
        if Path(name).name != name or not results_csv.exists():
            raise FileNotFoundError(f"'{name}' 실험 결과가 없습니다. search_results로 이름을 확인해 주세요.")
        path = plot_results(results_csv, x, y, group_by, where=where)
        return {"image": str(path)}

    def _log(self, tool: str, arguments: dict[str, Any], result: dict[str, Any]) -> None:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": tool, "arguments": arguments, "result": result}
        with open(self.results_dir / "agent_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _summarize(meta: dict[str, Any], results_csv: Path) -> dict[str, Any]:
    """조건별로 seed 평균을 낸 요약. Agent에게 CSV 전체 대신 이것을 준다."""
    keys = list(meta["vary"])
    with open(results_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)

    conditions = []
    for values, group in groups.items():
        metrics = {
            column: round(sum(float(r[column]) for r in group) / len(group), 4)
            for column in group[0]
            if column in ("throughput_per_hour", "avg_cycle_time")
            or column.endswith((".avg_wait", ".utilization"))
        }
        labels = {
            column: Counter(r[column] for r in group).most_common(1)[0][0]
            for column in ("bottleneck", "limited_by")
            if column in group[0]  # limited_by는 예전 결과표에는 없다
        }
        conditions.append({"condition": dict(zip(keys, values)), **labels, **metrics})
    return {"name": meta["name"], "vary": meta["vary"], "seeds": meta["seeds"], "conditions": conditions}
