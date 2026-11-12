import csv

import pytest

from openfab.agent import Toolbox
from openfab.harness import expand, load_experiment, run_experiment
from openfab.harness.conditions import experiment_from_dict
from openfab.sim.config import ConfigError


def test_example_experiment_expands_all_combinations():
    experiment = load_experiment("configs/experiments/example.yaml")
    assert len(expand(experiment)) == 9


def test_run_writes_one_row_per_condition_and_seed(tmp_path):
    experiment = load_experiment("configs/experiments/example.yaml")
    folder = run_experiment(experiment, tmp_path)
    with open(folder / "results.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 9 * 3
    assert (folder / "experiment.yaml").exists()


def test_rerun_gives_identical_csv(tmp_path):
    experiment = load_experiment("configs/experiments/example.yaml")
    first = (run_experiment(experiment, tmp_path / "a") / "results.csv").read_text()
    second = (run_experiment(experiment, tmp_path / "b") / "results.csv").read_text()
    assert first == second


def test_unknown_process_is_rejected_before_running():
    experiment = load_experiment("configs/experiments/example.yaml")
    with pytest.raises(ConfigError):
        experiment_from_dict({**experiment.to_dict(), "vary": {"processes.diffusion.machines": [1]}})


def test_agent_needs_approval(tmp_path):
    toolbox = Toolbox(results_dir=tmp_path, approve=lambda plan: False)
    result = toolbox.call("run_experiment", {"name": "t", "vary": {"release.lots": [5]}, "reason": "test"})
    assert result["status"] == "rejected"
    assert not (tmp_path / "t").exists()
    assert (tmp_path / "agent_log.jsonl").exists()


def test_agent_search_reports_missing_data(tmp_path):
    toolbox = Toolbox(results_dir=tmp_path, approve=lambda plan: True)
    assert toolbox.call("search_results", {"query": "nothing"})["experiments"] == []

    toolbox.call("run_experiment", {"name": "lots", "vary": {"release.lots": [5, 10]}, "reason": "test"})
    found = toolbox.call("search_results", {"query": "lots"})["experiments"]
    assert len(found[0]["conditions"]) == 2


def test_randomness_can_be_varied(tmp_path):
    base = load_experiment("configs/experiments/example.yaml").base
    experiment = experiment_from_dict({
        "name": "arrival", "base": base, "seeds": [1],
        "vary": {"randomness.arrival": ["fixed", "exponential"], "release.lots": [50]},
    })
    with open(run_experiment(experiment, tmp_path) / "results.csv", encoding="utf-8") as f:
        fixed, random = list(csv.DictReader(f))
    # 투입이 들쭉날쭉하면 같은 투입률에서도 첫 공정 대기가 늘어난다
    assert float(random["photo.avg_wait"]) > float(fixed["photo.avg_wait"])
    with pytest.raises(ConfigError):
        experiment_from_dict({**experiment.to_dict(), "vary": {"randomness.arrival": ["weibull"]}})


def test_limited_by_tells_release_from_process(tmp_path):
    """투입이 모자라면 release, 넘치면 처리능력이 가장 작은 공정 (photo 2대면 inspection)."""
    experiment = load_experiment("configs/experiments/example.yaml")
    with open(run_experiment(experiment, tmp_path) / "results.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    answer = {(r["processes.photo.machines"], r["release.interval"]): r["limited_by"] for r in rows}
    assert answer[("1", "24")] == "release"     # 2.5 Lot/h < photo 2.86
    assert answer[("1", "15")] == "photo"       # 4.0 Lot/h > photo 2.86
    assert answer[("2", "20")] == "release"     # 3.0 Lot/h < inspection 3.33
    assert answer[("2", "15")] == "inspection"
    assert answer[("3", "15")] == "inspection"  # photo를 더 늘려도 그대로


def test_plot_where_keeps_only_matching_rows(tmp_path):
    from openfab.harness.plot import plot_results

    experiment = load_experiment("configs/experiments/example.yaml")
    results = run_experiment(experiment, tmp_path) / "results.csv"
    x, y = "processes.photo.machines", "throughput_per_hour"
    path = plot_results(results, x, y, where={"release.interval": 15})
    assert path.name == f"{y}_by_{x}_release.interval=15.png" and path.stat().st_size > 0
    with pytest.raises(ValueError):
        plot_results(results, x, y, where={"release.interval": 99})
    with pytest.raises(KeyError):
        plot_results(results, x, y, where={"release.speed": 1})


def test_agent_plot_tool_accepts_where(tmp_path):
    toolbox = Toolbox(results_dir=tmp_path, approve=lambda plan: True)
    toolbox.call("run_experiment", {
        "name": "p", "reason": "test", "seeds": [1],
        "vary": {"processes.photo.machines": [1, 2], "release.interval": [24, 15], "release.lots": [20]},
    })
    plotted = toolbox.call("plot", {
        "name": "p", "x": "processes.photo.machines", "y": "throughput_per_hour", "where": {"release.interval": 15},
    })
    assert plotted["image"].endswith(".png")
    assert "error" in toolbox.call("plot", {"name": "../p", "x": "seed", "y": "makespan"})
