"""관계식(openfab.theory)과 시뮬레이션 결과 비교.

theory의 함수가 아직 비어 있으면(NotImplementedError) 해당 테스트는 건너뛴다.
"""

import functools

import pytest

from openfab import theory
from openfab.sim import EventKind, load_factory, simulate
from openfab.sim.config import factory_from_dict


def needs_theory(test):
    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        try:
            return test(*args, **kwargs)
        except NotImplementedError:
            pytest.skip("theory 관계식이 아직 비어 있음 (TODO(명민))")

    return wrapper


def flooded(config, lots=300):
    """Lot을 한꺼번에 많이 넣고 무작위성을 없앤 공장: 최대 처리능력 확인용."""
    data = {
        "processes": [vars(p) for p in config.processes],
        "release": {"lots": lots, "interval": 0},
        "randomness": {"process_time": "fixed", "arrival": "fixed"},
    }
    return factory_from_dict(data)


def single_station(machines, process_time, interval, dist="exponential", lots=20000):
    return factory_from_dict({
        "processes": [{"name": "only", "machines": machines, "process_time": process_time}],
        "release": {"lots": lots, "interval": interval},
        "randomness": {"process_time": dist, "arrival": dist},
    })


@needs_theory
def test_bottleneck_matches_simulation():
    config = flooded(load_factory("configs/factory.yaml"))
    assert theory.bottleneck(config) == simulate(config, seed=0).bottleneck


@needs_theory
def test_max_throughput_matches_flooded_factory():
    config = flooded(load_factory("configs/factory.yaml"))
    result = simulate(config, seed=0)
    assert result.throughput_per_hour / 60 == pytest.approx(theory.max_throughput(config), rel=0.05)


@needs_theory
def test_expected_utilization_matches_simulation():
    config = single_station(machines=2, process_time=14, interval=10)
    result = simulate(config, seed=1)
    expected = theory.expected_utilization(config.processes[0], arrival_interval=10)
    assert result.processes["only"].utilization == pytest.approx(expected, abs=0.03)


@needs_theory
def test_littles_law_matches_simulation():
    result = simulate(load_factory("configs/factory.yaml"), seed=3)

    # 시뮬레이션에서 공장 안 Lot 수의 시간 평균을 직접 잰다
    changes = sorted(
        (e.time, +1 if e.kind is EventKind.LOT_RELEASED else -1)
        for e in result.events
        if e.kind in (EventKind.LOT_RELEASED, EventKind.LOT_COMPLETED)
    )
    area, wip, last = 0.0, 0, 0.0
    for time, delta in changes:
        area += wip * (time - last)
        wip, last = wip + delta, time
    measured_wip = area / result.makespan

    expected = theory.littles_law_wip(result.completed_lots / result.makespan, result.avg_cycle_time)
    assert measured_wip == pytest.approx(expected, rel=1e-6)


@needs_theory
@pytest.mark.parametrize("machines, process_time", [(1, 7), (1, 9), (2, 16)])
def test_expected_wait_close_to_simulation(machines, process_time):
    # 근사식이므로 오차를 넉넉히 허용 (가동률 0.7~0.9)
    config = single_station(machines, process_time, interval=10)
    result = simulate(config, seed=2)
    expected = theory.expected_wait(config.processes[0], arrival_interval=10, arrival_cv=1, process_cv=1)
    assert result.processes["only"].avg_wait == pytest.approx(expected, rel=0.25)
