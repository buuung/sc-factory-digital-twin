"""관계식(이론값): 시뮬레이션을 돌리지 않고 손으로 계산하는 예상값.

TODO(명민): 각 함수의 식을 조사해서 채워 주세요.
  - 식, 출처, 가정(어떤 조건에서 맞는 식인지)은 docs/formulas.md에 함께 정리합니다.
  - 채우면 tests/test_theory.py가 시뮬레이션 결과와 자동으로 비교합니다.
    (아직 비어 있는 함수의 테스트는 건너뜁니다: `pytest -rs`로 확인)
  - 시간 단위는 분(min)입니다.

시뮬레이션 결과와 이론값이 다르면 둘 중 하나가 틀린 것이므로, 어느 쪽인지 같이 확인합니다.
"""

from __future__ import annotations

from openfab.sim.config import FactoryConfig, ProcessConfig


def process_capacity(process: ProcessConfig) -> float:
    """공정 하나가 1분에 최대 처리할 수 있는 Lot 수.

    입력: 장비 수(process.machines), Lot 1개 처리시간(process.process_time)
    힌트 키워드: 처리능력(capacity), 공정 처리율
    """
    raise NotImplementedError("TODO(명민)")


def bottleneck(config: FactoryConfig) -> str:
    """병목 공정의 이름.

    힌트: 위의 process_capacity를 이용. 같은 값이 여러 개면 앞쪽 공정
    """
    raise NotImplementedError("TODO(명민)")


def max_throughput(config: FactoryConfig) -> float:
    """공장 전체가 1분에 최대 만들 수 있는 Lot 수 (투입이 충분히 많을 때).

    힌트 키워드: 병목 처리율, bottleneck rate
    """
    raise NotImplementedError("TODO(명민)")


def expected_utilization(process: ProcessConfig, arrival_interval: float) -> float:
    """Lot이 arrival_interval분마다 평균 1개씩 들어올 때 이 공정의 장비 가동률 (0~1).

    힌트 키워드: 가동률(utilization), 도착률, 처리율
    """
    raise NotImplementedError("TODO(명민)")


def littles_law_wip(throughput: float, cycle_time: float) -> float:
    """공장 안에 평균 몇 개의 Lot이 있는지 (WIP, 재공).

    입력: 1분당 생산량, 평균 사이클타임(분)
    힌트 키워드: Little's Law
    """
    raise NotImplementedError("TODO(명민)")


def expected_wait(
    process: ProcessConfig,
    arrival_interval: float,
    arrival_cv: float,
    process_cv: float,
) -> float:
    """이 공정 대기열에서 Lot이 기다리는 평균 시간(분)의 근사값.

    입력
      arrival_interval  평균 도착 간격
      arrival_cv        도착 간격의 변동계수 (표준편차 ÷ 평균). fixed면 0, exponential이면 1
      process_cv        처리시간의 변동계수. fixed면 0, exponential이면 1
    힌트 키워드: Kingman 공식(VUT 식), 장비가 여러 대면 Sakasegawa 근사, Factory Physics
    가동률이 100%에 가까울수록 대기시간이 폭발적으로 늘어나는지 확인해 보세요.
    """
    raise NotImplementedError("TODO(명민)")
