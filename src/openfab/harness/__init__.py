"""[2층] 하네스: 조건표를 받아 시뮬레이터를 반복 실행하고 결과를 기록한다.

사람이든 AI Agent든 실험은 이 하네스를 통해서만 실행한다.
"""

from openfab.harness.conditions import Experiment, expand, load_experiment
from openfab.harness.runner import run_experiment

__all__ = ["Experiment", "expand", "load_experiment", "run_experiment"]
