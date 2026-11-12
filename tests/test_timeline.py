"""사건 기록 → 장비 상태 타임라인 (IDLE ↔ PROCESSING)."""

import csv

import pytest
import yaml

from openfab.harness.trace import parse_overrides, run_trace
from openfab.sim import EquipmentState, load_factory, machine_timeline, simulate, state_at
from openfab.sim.config import factory_from_dict


def fixed_factory(lots=2):
    return factory_from_dict({
        "processes": [
            {"name": "photo", "machines": 1, "process_time": 10},
            {"name": "etch", "machines": 2, "process_time": 5},
        ],
        "release": {"lots": lots, "interval": 0},
        "randomness": {"process_time": "fixed", "arrival": "fixed"},
    })


def test_states_follow_events():
    # photo: LOT001 0~10, LOT002 10~20. etch: LOT001은 #0에서 10~15, LOT002는 #1에서 20~25. makespan 25
    # (빈 장비는 먼저 비워진 순서로 배정되므로 방금 일을 끝낸 #0보다 계속 쉬던 #1이 먼저 쓰인다)
    timeline = machine_timeline(simulate(fixed_factory(), seed=0))
    photo = [(i.state, i.start, i.end, i.lot_id) for i in timeline if i.process == "photo"]
    assert photo == [
        (EquipmentState.PROCESSING, 0, 10, "LOT001"),
        (EquipmentState.PROCESSING, 10, 20, "LOT002"),
        (EquipmentState.IDLE, 20, 25, None),
    ]
    etch = {m: [(i.state, i.start, i.end) for i in timeline if (i.process, i.machine) == ("etch", m)] for m in (0, 1)}
    assert etch[0] == [
        (EquipmentState.IDLE, 0, 10), (EquipmentState.PROCESSING, 10, 15), (EquipmentState.IDLE, 15, 25),
    ]
    assert etch[1] == [(EquipmentState.IDLE, 0, 20), (EquipmentState.PROCESSING, 20, 25)]
    assert state_at(timeline, "etch", 0, 5) is EquipmentState.IDLE
    assert state_at(timeline, "etch", 0, 12) is EquipmentState.PROCESSING


def test_each_machine_is_covered_without_gaps_and_matches_utilization():
    result = simulate(load_factory("configs/factory.yaml"), seed=4)
    timeline = machine_timeline(result)
    for name, stats in result.processes.items():
        busy = 0.0
        for machine in range(stats.machines):
            intervals = [i for i in timeline if (i.process, i.machine) == (name, machine)]
            assert intervals[0].start == 0
            assert intervals[-1].end == pytest.approx(result.makespan)
            for before, after in zip(intervals, intervals[1:]):
                assert before.end == after.start
            busy += sum(i.duration for i in intervals if i.state is EquipmentState.PROCESSING)
        # 타임라인에서 다시 계산한 가동률이 시뮬레이터가 낸 값과 같아야 한다
        assert busy / (stats.machines * result.makespan) == pytest.approx(stats.utilization)


def test_trace_writes_files_and_is_reproducible(tmp_path):
    with open("configs/factory.yaml", encoding="utf-8") as f:
        base = yaml.safe_load(f)
    override = parse_overrides(["processes.photo.machines=2", "release.lots=20", "randomness.arrival=exponential"])
    assert override == {"processes.photo.machines": 2, "release.lots": 20, "randomness.arrival": "exponential"}

    first = run_trace(base, seed=3, override=override, out_dir=tmp_path / "a")
    second = run_trace(base, seed=3, override=override, out_dir=tmp_path / "b")
    for name in ("events.csv", "timeline.csv"):
        assert (first / name).read_text() == (second / name).read_text()
    assert (first / "timeline.png").stat().st_size > 0

    with open(first / "events.csv", encoding="utf-8") as f:
        events = list(csv.DictReader(f))
    assert sum(e["kind"] == "lot_completed" for e in events) == 20
    assert {e["machine"] for e in events if e["process"] == "photo" and e["kind"] == "started"} == {"0", "1"}
