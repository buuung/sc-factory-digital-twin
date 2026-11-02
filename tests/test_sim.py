import pytest

from openfab.sim import load_factory, simulate
from openfab.sim.config import ConfigError, factory_from_dict


def fixed_factory(lots=1, interval=0, photo_machines=1):
    return factory_from_dict({
        "processes": [
            {"name": "photo", "machines": photo_machines, "process_time": 10},
            {"name": "etch", "machines": 1, "process_time": 5},
        ],
        "release": {"lots": lots, "interval": interval},
        "randomness": {"process_time": "fixed", "arrival": "fixed"},
    })


def test_single_lot_cycle_time_is_sum_of_process_times():
    result = simulate(fixed_factory(), seed=0)
    assert result.completed_lots == 1
    assert result.avg_cycle_time == 15
    assert all(stats.avg_wait == 0 for stats in result.processes.values())


def test_second_lot_waits_at_busy_machine():
    # 두 Lot이 동시에 들어오면 두 번째 Lot은 photo에서 10분 기다린다
    result = simulate(fixed_factory(lots=2), seed=0)
    assert result.lots[1].waits["photo"] == 10
    assert result.makespan == 25


def test_adding_machine_at_bottleneck_removes_wait():
    result = simulate(fixed_factory(lots=2, photo_machines=2), seed=0)
    assert result.lots[1].waits["photo"] == 0


def test_busy_time_matches_utilization():
    result = simulate(fixed_factory(lots=2), seed=0)
    # photo: 10분 × 2 Lot / (장비 1대 × 25분)
    assert result.processes["photo"].utilization == pytest.approx(20 / 25)


def test_same_seed_same_result():
    config = load_factory("configs/factory.yaml")
    assert simulate(config, seed=7).summary() == simulate(config, seed=7).summary()
    assert simulate(config, seed=7).summary() != simulate(config, seed=8).summary()


def test_unknown_field_is_rejected():
    with pytest.raises(ConfigError):
        factory_from_dict({
            "processes": [{"name": "photo", "machines": 1, "process_time": 10, "speed": 2}],
            "release": {"lots": 1, "interval": 0},
        })
