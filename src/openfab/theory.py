"""관계식(이론값): 시뮬레이션을 돌리지 않고 손으로 계산하는 예상값.

처리능력·병목·최대 생산량·가동률은 명민 조사(docs/process_params.md) 기준으로 채웠다.
TODO(명민): 남은 함수(Little's Law, 대기시간 근사)의 식을 조사해서 채워 주세요.
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
    식: 장비 수 / 처리시간  (Lot/h로 보려면 × 60)
    가정: 장비가 쉬지 않고 일한다(고장·셋업 교체 없음). 처리시간이 0이면 무한대
    """
    if process.process_time == 0:
        return float("inf")
    return process.machines / process.process_time


def bottleneck(config: FactoryConfig) -> str:
    """병목 공정의 이름.

    처리능력이 가장 작은 공정. 같은 값이 여러 개면 앞쪽 공정(max/min은 처음 것을 고른다)
    """
    return min(config.processes, key=process_capacity).name


def max_throughput(config: FactoryConfig) -> float:
    """공장 전체가 1분에 최대 만들 수 있는 Lot 수 (투입이 충분히 많을 때).

    식: 병목 공정의 처리능력. 한 줄로 지나가는 흐름이라 가장 느린 공정보다 빨리 나올 수 없다
    """
    return min(process_capacity(p) for p in config.processes)


def expected_utilization(process: ProcessConfig, arrival_interval: float) -> float:
    """Lot이 arrival_interval분마다 평균 1개씩 들어올 때 이 공정의 장비 가동률 (0~1).

    식: 도착률 / 처리능력 = (1 / arrival_interval) / process_capacity
    가정: 정상 상태, 도착률 < 처리능력. 넘으면 1(100%)로 자른다(대기열이 계속 늘어남)
    """
    if arrival_interval == 0:
        return 1.0
    return min(1.0, (1 / arrival_interval) / process_capacity(process))


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
