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
