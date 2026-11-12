"""이벤트 기록에서 장비별 상태 타임라인을 만든다.

시뮬레이터는 "처리 시작", "처리 끝" 같은 사건(Event)만 남긴다. 장비 입장에서 보면
사건은 상태가 바뀌는 순간이므로, 사건을 시간순으로 따라가면 각 장비가 언제 IDLE이고
언제 PROCESSING이었는지 구간으로 되살릴 수 있다 (임베디드의 상태 기계와 같은 방식).

    IDLE --STARTED--> PROCESSING --FINISHED--> IDLE

이 타임라인이 [4층] 디지털 트윈에서 장비 색을 칠할 때 쓰는 입력이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from openfab.sim.model import EquipmentState, EventKind, SimResult


@dataclass(frozen=True)
class StateInterval:
    process: str
    machine: int  # 공정 안에서 몇 번째 장비인지 (0부터)
    state: EquipmentState
    start: float
    end: float
    lot_id: str | None = None  # PROCESSING일 때 처리한 Lot

    @property
    def duration(self) -> float:
        return self.end - self.start


def machine_timeline(result: SimResult) -> list[StateInterval]:
    """모든 장비의 상태 구간. 장비마다 0분부터 makespan까지 빈틈없이 이어진다."""
    last_change = {
        (name, machine): 0.0 for name, stats in result.processes.items() for machine in range(stats.machines)
    }
    intervals: list[StateInterval] = []

    for event in result.events:  # 시뮬레이터가 시간순으로 기록한다
        if event.kind not in (EventKind.STARTED, EventKind.FINISHED):
            continue
        key = (event.process, event.machine)
        if event.kind is EventKind.STARTED:
            state, lot_id = EquipmentState.IDLE, None  # 지금까지 쉬고 있었다
        else:
            state, lot_id = EquipmentState.PROCESSING, event.lot_id  # 지금까지 이 Lot을 처리했다
        if event.time > last_change[key] or state is EquipmentState.PROCESSING:
            intervals.append(StateInterval(*key, state, last_change[key], event.time, lot_id))
        last_change[key] = event.time

    for key, since in last_change.items():  # 마지막 Lot을 끝낸 뒤 남은 시간은 IDLE
        if result.makespan > since:
            intervals.append(StateInterval(*key, EquipmentState.IDLE, since, result.makespan))
    return sorted(intervals, key=lambda i: (i.process, i.machine, i.start))


def state_at(timeline: list[StateInterval], process: str, machine: int, time: float) -> EquipmentState:
    """어떤 시각에 그 장비가 어떤 상태였는지. 경계 시각은 새로 시작한 상태로 본다."""
    for interval in timeline:
        if interval.process == process and interval.machine == machine and interval.start <= time < interval.end:
            return interval.state
    return EquipmentState.IDLE
