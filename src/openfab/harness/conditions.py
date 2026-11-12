"""실험 조건표를 읽고, 바꿀 값의 모든 조합으로 펼친다."""

from __future__ import annotations

import copy
import itertools
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from openfab.sim.config import ConfigError, FactoryConfig, factory_from_dict

VARY_KEYS = (
    "processes.<공정>.machines",
    "processes.<공정>.process_time",
    "release.lots",
    "release.interval",
    "randomness.process_time",
    "randomness.arrival",
)

Override = dict[str, Any]  # 예: {"processes.photo.machines": 3, "release.lots": 20}


@dataclass
class Experiment:
    name: str
    base: dict[str, Any]  # 기준 공장 설정 (YAML을 읽은 dict)
    seeds: list[int]
    vary: dict[str, list[Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "base": self.base, "seeds": self.seeds, "vary": self.vary}


def load_experiment(path: str | Path, root: str | Path = ".") -> Experiment:
    """조건표 YAML을 읽는다. base 경로는 root 기준으로 찾는다."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    base = data.get("base")
    if isinstance(base, str):
        with open(Path(root) / base, encoding="utf-8") as f:
            data["base"] = yaml.safe_load(f)
    return experiment_from_dict(data)


def experiment_from_dict(data: dict[str, Any]) -> Experiment:
    unknown = set(data) - {"name", "base", "seeds", "vary"}
    if unknown:
        raise ConfigError(f"조건표에 알 수 없는 항목이 있습니다: {sorted(unknown)}")
    name = data.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        # 이름이 결과 폴더 이름이 되므로 경로 문자(/, ..)를 막는다. Agent가 지은 이름도 여기서 걸러진다
        raise ConfigError(f"조건표의 name은 영문·숫자·밑줄·하이픈만 쓸 수 있습니다: {name!r}")
    if not isinstance(data.get("base"), dict):
        raise ConfigError("조건표의 base는 공장 설정이어야 합니다")
    seeds = data.get("seeds") or [0]
    vary = data.get("vary") or {}
    for key, values in vary.items():
        if not isinstance(values, list) or not values:
            raise ConfigError(f"vary.{key}는 값 목록이어야 합니다: {values!r}")

    experiment = Experiment(name=data["name"], base=data["base"], seeds=list(seeds), vary=dict(vary))
    for override in expand(experiment):  # 실행 전에 모든 조합이 유효한지 먼저 확인
        build_factory(experiment.base, override)
    return experiment


def expand(experiment: Experiment) -> list[Override]:
    """vary의 모든 조합을 만든다. vary가 비어 있으면 기준 설정 하나."""
    keys = list(experiment.vary)
    return [dict(zip(keys, values)) for values in itertools.product(*experiment.vary.values())]


def build_factory(base: dict[str, Any], override: Override) -> FactoryConfig:
    data = copy.deepcopy(base)
    for key, value in override.items():
        _set_value(data, key, value)
    return factory_from_dict(data)


def _set_value(data: dict[str, Any], key: str, value: Any) -> None:
    parts = key.split(".")
    if len(parts) == 3 and parts[0] == "processes":
        _, name, field_name = parts
        if field_name not in ("machines", "process_time"):
            raise ConfigError(f"공정에서 바꿀 수 없는 항목입니다: {key}")
        for process in data["processes"]:
            if process.get("name") == name:
                process[field_name] = value
                return
        raise ConfigError(f"없는 공정입니다: {name} ({key})")
    if len(parts) == 2 and parts[0] == "release" and parts[1] in ("lots", "interval"):
        data.setdefault("release", {})[parts[1]] = value
        return
    if len(parts) == 2 and parts[0] == "randomness" and parts[1] in ("process_time", "arrival"):
        data.setdefault("randomness", {})[parts[1]] = value
        return
    raise ConfigError(f"바꿀 수 없는 항목입니다: {key} (바꿀 수 있는 값: {', '.join(VARY_KEYS)})")
