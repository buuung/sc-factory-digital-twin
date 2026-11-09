# 관계식 정리

> TODO(명민): 조사한 관계식을 아래 형식으로 정리하고, 같은 식을 `src/openfab/theory.py`에 코드로 채워 주세요.
> `uv run pytest -rs tests/test_theory.py`로 시뮬레이션 결과와 맞는지 확인할 수 있습니다.

## 작성 형식

각 관계식마다 다음을 적습니다.

- **식**: 기호와 각 기호의 뜻·단위
- **출처**: 책·논문·강의 (쪽수까지)
- **가정**: 어떤 조건에서 맞는 식인지 (예: 정상 상태, 도착이 무작위, 장비 1대)
- **우리 공장에서의 값**: `configs/factory.yaml` 숫자를 넣어 손으로 계산한 결과
- **시뮬레이션과 비교**: 맞는지, 다르면 왜 다른지
- **코드**: `theory.py`의 함수 이름

## 채울 관계식

| 관계식 | `theory.py` 함수 | 비교 테스트 |
| --- | --- | --- |
| 공정 처리능력 | `process_capacity` | `test_max_throughput_matches_flooded_factory` |
| 병목 판정 | `bottleneck` | `test_bottleneck_matches_simulation` |
| 공장 최대 생산량 | `max_throughput` | `test_max_throughput_matches_flooded_factory` |
| 장비 가동률 | `expected_utilization` | `test_expected_utilization_matches_simulation` |
| Little's Law (WIP) | `littles_law_wip` | `test_littles_law_matches_simulation` |
| 대기시간 근사 | `expected_wait` | `test_expected_wait_close_to_simulation` |

## 1. 공정 처리능력

- **식**: 처리능력 μ = c / t (Lot/분). c: 장비 수, t: Lot 1개 평균 처리시간(분). Lot/h로 보려면 × 60
- **출처**: 명민 조사 ([process_params.md](process_params.md))
- **가정**: 장비가 쉬지 않고 일함 (고장·셋업 교체 없음)
- **우리 공장에서의 값**: photo 2.86 · etch 3.43 · deposition 4.80 · cmp 3.75 · inspection 3.33 Lot/h
- **코드**: `process_capacity`

## 2. 병목 판정

- **식**: 처리능력 μ가 가장 작은 공정. 같으면 앞쪽 공정
- **우리 공장에서의 값**: photo (2.86 Lot/h). photo 2대면 inspection (3.33)
- **코드**: `bottleneck`

## 3. 공장 최대 생산량

- **식**: TH_max = min(μ). 한 줄로 지나가는 흐름이라 가장 느린 공정보다 빨리 나올 수 없음
- **가정**: 투입이 충분히 많음, 재진입 없음
- **우리 공장에서의 값**: 2.86 Lot/h. photo 2대면 3.33 Lot/h (+17%)
- **코드**: `max_throughput`

## 4. 장비 가동률

- **식**: u = λ / μ. λ = 1 / 투입 간격. λ ≥ μ이면 1로 자름 (대기열이 계속 늘어남)
- **가정**: 정상 상태, 도착률 < 처리능력
- **우리 공장에서의 값** (투입 간격 24분): photo 87.5% · etch 72.9% · deposition 52.1% · cmp 66.7% · inspection 75.0%
- **시뮬레이션과 비교**: `tests/test_sanity.py`
- **코드**: `expected_utilization`

## 5. Little's Law

TODO(명민)

## 6. 대기시간 근사

TODO(명민)
