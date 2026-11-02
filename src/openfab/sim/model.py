"""시뮬레이션 결과를 담는 자료형."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EquipmentState(Enum):
    IDLE = "idle"              # 대기 (일감 없음)
    PROCESSING = "processing"  # 처리 중


class EventKind(Enum):
    LOT_RELEASED = "lot_released"  # Lot 투입
    QUEUED = "queued"              # 공정 도착, 대기열 진입
    STARTED = "started"            # 처리 시작
    FINISHED = "finished"          # 처리 끝
    LOT_COMPLETED = "lot_completed"  # 마지막 공정까지 완료


@dataclass(frozen=True)
class Event:
    time: float
    kind: EventKind
    lot_id: str
    process: str | None = None
    machine: int | None = None  # 공정 안에서 몇 번째 장비인지 (0부터)


@dataclass
class LotRecord:
    lot_id: str
    released_at: float
    completed_at: float | None = None
    waits: dict[str, float] = field(default_factory=dict)  # 공정별 대기시간

    @property
    def cycle_time(self) -> float | None:
        if self.completed_at is None:
            return None
        return self.completed_at - self.released_at


@dataclass(frozen=True)
class ProcessStats:
    machines: int
    avg_wait: float
    utilization: float  # 0~1


@dataclass
class SimResult:
    seed: int
    makespan: float  # 첫 투입부터 마지막 Lot 완료까지 걸린 시간
    lots: list[LotRecord]
    processes: dict[str, ProcessStats]
    events: list[Event]

    @property
    def completed_lots(self) -> int:
        return sum(1 for lot in self.lots if lot.completed_at is not None)

    @property
    def throughput_per_hour(self) -> float:
        """시간당 완성 Lot 수 (시간 단위가 분이라고 가정)."""
        if self.makespan == 0:
            return 0.0
        return self.completed_lots / self.makespan * 60

    @property
    def avg_cycle_time(self) -> float:
        times = [lot.cycle_time for lot in self.lots if lot.cycle_time is not None]
        return sum(times) / len(times) if times else 0.0

    @property
    def bottleneck(self) -> str:
        """가동률이 가장 높은 공정."""
        return max(self.processes, key=lambda name: self.processes[name].utilization)

    def summary(self) -> dict[str, float | int | str]:
        """결과표(CSV) 한 줄로 쓰기 위한 평평한 dict."""
        row: dict[str, float | int | str] = {
            "seed": self.seed,
            "completed_lots": self.completed_lots,
            "makespan": round(self.makespan, 3),
            "throughput_per_hour": round(self.throughput_per_hour, 4),
            "avg_cycle_time": round(self.avg_cycle_time, 3),
            "bottleneck": self.bottleneck,
        }
        for name, stats in self.processes.items():
            row[f"{name}.avg_wait"] = round(stats.avg_wait, 3)
            row[f"{name}.utilization"] = round(stats.utilization, 4)
        return row
