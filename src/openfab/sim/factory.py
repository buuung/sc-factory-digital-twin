"""SimPy로 Lot이 공정을 순서대로 지나가는 과정을 계산한다."""

from __future__ import annotations

import random

import simpy

from openfab.sim.config import FactoryConfig, ProcessConfig
from openfab.sim.model import Event, EventKind, LotRecord, ProcessStats, SimResult


class _Station:
    """한 공정의 장비 묶음. 비어 있는 장비 번호를 Store로 관리한다."""

    def __init__(self, env: simpy.Environment, config: ProcessConfig) -> None:
        self.config = config
        self.machines = simpy.Store(env, capacity=config.machines)
        self.machines.items = list(range(config.machines))
        self.busy_time = 0.0
        self.waits: list[float] = []


def simulate(config: FactoryConfig, seed: int) -> SimResult:
    """설정과 seed가 같으면 항상 같은 결과를 돌려준다."""
    rng = random.Random(seed)
    env = simpy.Environment()
    stations = [_Station(env, p) for p in config.processes]
    events: list[Event] = []
    lots: list[LotRecord] = []

    def sample(mean: float, dist: str) -> float:
        if dist == "fixed" or mean == 0:
            return mean
        return rng.expovariate(1 / mean)

    def lot_flow(lot: LotRecord):
        for station in stations:
            name = station.config.name
            arrived = env.now
            events.append(Event(env.now, EventKind.QUEUED, lot.lot_id, name))

            machine = yield station.machines.get()
            wait = env.now - arrived
            station.waits.append(wait)
            lot.waits[name] = wait
            events.append(Event(env.now, EventKind.STARTED, lot.lot_id, name, machine))

            duration = sample(station.config.process_time, config.process_time_dist)
            yield env.timeout(duration)
            station.busy_time += duration
            events.append(Event(env.now, EventKind.FINISHED, lot.lot_id, name, machine))
            yield station.machines.put(machine)

        lot.completed_at = env.now
        events.append(Event(env.now, EventKind.LOT_COMPLETED, lot.lot_id))

    def release():
        for i in range(config.release.lots):
            lot = LotRecord(lot_id=f"LOT{i + 1:03d}", released_at=env.now)
            lots.append(lot)
            events.append(Event(env.now, EventKind.LOT_RELEASED, lot.lot_id))
            env.process(lot_flow(lot))
            if i < config.release.lots - 1:
                yield env.timeout(sample(config.release.interval, config.arrival_dist))

    env.process(release())
    env.run()

    makespan = env.now
    processes = {
        s.config.name: ProcessStats(
            machines=s.config.machines,
            avg_wait=sum(s.waits) / len(s.waits) if s.waits else 0.0,
            utilization=s.busy_time / (s.config.machines * makespan) if makespan else 0.0,
        )
        for s in stations
    }
    return SimResult(seed=seed, makespan=makespan, lots=lots, processes=processes, events=events)
