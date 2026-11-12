"""명민 조사표(docs/process_params.md)의 손계산 결과와 시뮬레이션 비교 (상식 검증).

시뮬레이터 결과가 이 범위에서 크게 벗어나면 코드나 configs/factory.yaml을 의심한다.
"""

import dataclasses

import pytest

from openfab import theory
from openfab.sim import load_factory, simulate

# 조사표의 손계산 값
CAPACITY_PER_HOUR = {"photo": 2.86, "etch": 3.43, "deposition": 4.80, "cmp": 3.75, "inspection": 3.33}
UTILIZATION_AT_24MIN = {"photo": 0.875, "etch": 0.729, "deposition": 0.521, "cmp": 0.667, "inspection": 0.750}


def base(lots=None, interval=None, process_time="exponential", **machines):
    config = load_factory("configs/factory.yaml")
    processes = tuple(
        dataclasses.replace(p, machines=machines.get(p.name, p.machines)) for p in config.processes
    )
    release = dataclasses.replace(
        config.release,
        lots=lots or config.release.lots,
        interval=config.release.interval if interval is None else interval,
    )
    return dataclasses.replace(config, processes=processes, release=release, process_time_dist=process_time)


def test_capacity_matches_hand_calculation():
    config = base()
    capacity = {p.name: theory.process_capacity(p) * 60 for p in config.processes}
    assert capacity == pytest.approx(CAPACITY_PER_HOUR, abs=0.005)
    assert theory.bottleneck(config) == "photo"


def test_expected_utilization_matches_hand_calculation():
    config = base()
    assert config.release.interval == 24
    expected = {p.name: theory.expected_utilization(p, 24) for p in config.processes}
    assert expected == pytest.approx(UTILIZATION_AT_24MIN, abs=0.001)


def test_simulated_utilization_matches_hand_calculation():
    """투입률 < 병목 용량: 생산량 ≈ 투입률, 가동률은 조사표대로, 대기는 photo 앞에 가장 많다."""
    result = simulate(base(lots=3000), seed=1)
    utilization = {name: s.utilization for name, s in result.processes.items()}
    assert utilization == pytest.approx(UTILIZATION_AT_24MIN, abs=0.03)
    assert result.throughput_per_hour == pytest.approx(2.5, rel=0.02)
    assert result.bottleneck == "photo"
    assert max(result.processes, key=lambda n: result.processes[n].avg_wait) == "photo"


def test_overload_caps_throughput_and_photo_queue_grows():
    """투입률(3.33 Lot/h) > 병목 용량(2.86): 생산량은 2.86 근처에서 멈추고 photo 대기가 계속 늘어난다."""
    result = simulate(base(lots=600, interval=18), seed=1)
    assert result.throughput_per_hour == pytest.approx(60 / 21, rel=0.03)

    waits = [lot.waits["photo"] for lot in result.lots]
    third = len(waits) // 3
    early, late = sum(waits[:third]) / third, sum(waits[-third:]) / third
    assert late > early * 2


def test_second_photo_machine_moves_bottleneck_to_inspection():
    """photo 2대: 병목이 inspection(3.33 Lot/h)으로 옮겨가고 최대 생산량은 약 +17%만 늘어난다."""
    before, after = base(), base(photo=2)
    assert theory.bottleneck(after) == "inspection"
    gain = theory.max_throughput(after) / theory.max_throughput(before) - 1
    assert gain == pytest.approx(0.167, abs=0.005)

    flooded = {"lots": 600, "interval": 0, "process_time": "fixed"}
    sim_before = simulate(base(**flooded), seed=0)
    sim_after = simulate(base(photo=2, **flooded), seed=0)
    assert sim_after.bottleneck == "inspection"
    assert sim_after.throughput_per_hour / sim_before.throughput_per_hour - 1 == pytest.approx(0.167, abs=0.02)
