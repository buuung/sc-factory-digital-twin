"""공장 설정(YAML)을 읽고 검증한다."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DISTRIBUTIONS = ("fixed", "exponential")
PROCESS_TIME_DISTRIBUTIONS = (*DISTRIBUTIONS, "triangular")


class ConfigError(ValueError):
    """설정 파일이 잘못되었을 때 발생한다."""


@dataclass(frozen=True)
class ProcessConfig:
    name: str
    machines: int
    process_time: float  # 평균 처리시간
    # triangular일 때 처리시간 모양 [최소, 최빈, 최대]. 뽑은 값은 평균이 process_time이 되도록 비율로 맞춘다
    # (그래서 하네스가 process_time만 바꿔도 모양은 유지된 채 평균만 옮겨간다)
    time_range: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class ReleaseConfig:
    lots: int
    interval: float


@dataclass(frozen=True)
class FactoryConfig:
    processes: tuple[ProcessConfig, ...]
    release: ReleaseConfig
    process_time_dist: str = "exponential"
    arrival_dist: str = "fixed"


def load_factory(path: str | Path) -> FactoryConfig:
    with open(path, encoding="utf-8") as f:
        return factory_from_dict(yaml.safe_load(f))


def factory_from_dict(data: dict[str, Any]) -> FactoryConfig:
    _check_keys(data, {"processes", "release", "randomness"}, "factory")

    raw_processes = data.get("processes")
    if not raw_processes:
        raise ConfigError("processes가 비어 있습니다")
    processes = tuple(_process_from_dict(p) for p in raw_processes)
    names = [p.name for p in processes]
    if len(names) != len(set(names)):
        raise ConfigError(f"공정 이름이 중복됩니다: {names}")

    raw_release = data.get("release") or {}
    _check_keys(raw_release, {"lots", "interval"}, "release")
    release = ReleaseConfig(
        lots=_positive_int(raw_release.get("lots"), "release.lots"),
        interval=_non_negative(raw_release.get("interval"), "release.interval"),
    )

    randomness = data.get("randomness") or {}
    _check_keys(randomness, {"process_time", "arrival"}, "randomness")
    process_time_dist = randomness.get("process_time", "exponential")
    arrival_dist = randomness.get("arrival", "fixed")
    if process_time_dist not in PROCESS_TIME_DISTRIBUTIONS:
        raise ConfigError(
            f"randomness.process_time은 {PROCESS_TIME_DISTRIBUTIONS} 중 하나여야 합니다: {process_time_dist!r}"
        )
    if arrival_dist not in DISTRIBUTIONS:
        raise ConfigError(f"randomness.arrival은 {DISTRIBUTIONS} 중 하나여야 합니다: {arrival_dist!r}")
    if process_time_dist == "triangular":
        missing = [p.name for p in processes if p.time_range is None]
        if missing:
            raise ConfigError(f"triangular에는 모든 공정의 time_range가 필요합니다: {missing}")

    return FactoryConfig(processes, release, process_time_dist, arrival_dist)


def _process_from_dict(data: dict[str, Any]) -> ProcessConfig:
    _check_keys(data, {"name", "machines", "process_time", "time_range"}, "process")
    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise ConfigError(f"공정 이름이 없습니다: {data}")
    return ProcessConfig(
        name=name,
        machines=_positive_int(data.get("machines"), f"{name}.machines"),
        process_time=_non_negative(data.get("process_time"), f"{name}.process_time"),
        time_range=_time_range(data.get("time_range"), name),
    )


def _time_range(value: Any, name: str) -> tuple[float, float, float] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ConfigError(f"{name}.time_range는 [최소, 최빈, 최대] 세 숫자여야 합니다: {value!r}")
    low, mode, high = (_non_negative(v, f"{name}.time_range") for v in value)
    if not low <= mode <= high or low == high:
        raise ConfigError(f"{name}.time_range는 최소 ≤ 최빈 ≤ 최대이고 최소 < 최대여야 합니다: {value!r}")
    return (low, mode, high)


def _check_keys(data: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise ConfigError(f"{where}에 알 수 없는 항목이 있습니다: {sorted(unknown)}")


def _positive_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"{name}는 1 이상의 정수여야 합니다: {value!r}")
    return value


def _non_negative(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ConfigError(f"{name}는 0 이상의 숫자여야 합니다: {value!r}")
    return float(value)
