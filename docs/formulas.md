# 관계식 정리

> 같은 식이 `src/openfab/theory.py`에 코드로 들어 있습니다.
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

- **식**: WIP = TH × CT (WIP: 공장 안 평균 Lot 수, TH: Lot/분, CT: 평균 사이클타임[분])
- **출처**: J. D. C. Little, "A Proof for the Queuing Formula: L = λW", *Operations Research* 9(3), 1961 · Hopp & Spearman, *Factory Physics* 3판 7장 (쪽수 확인 필요)
- **가정**: 관측 구간 안에서 들어온 Lot이 모두 나감. 시뮬레이션은 모든 Lot이 끝날 때까지 돌리므로 정확히 성립
- **우리 공장에서의 값** (투입 간격 24분, seed 0~9 평균): 2.45 Lot/h × 132분 ≈ **5.4 Lot**
- **시뮬레이션과 비교**: 이벤트 로그로 직접 잰 시간 평균 WIP와 일치 (상대오차 1e-6 이내)
- **의미**: 생산량이 그대로인데 공장 안 Lot이 24개로 쌓이면 사이클타임은 24 ÷ 2.45 ≈ 10시간이 된다. Lot을 많이 넣을수록 생산량은 그대로이고 기다리는 시간만 길어진다
- **코드**: `littles_law_wip`

## 6. 대기시간 근사

- **식** (VUT 식. 장비 m대는 Sakasegawa 근사, m = 1이면 Kingman 공식):

  대기 = (c_a² + c_e²) / 2 × u^(√(2(m+1)) − 1) / (m(1 − u)) × t

  V(변동) × U(가동률) × T(시간). c_a: 도착 간격 변동계수, c_e: 처리시간 변동계수 (표준편차 ÷ 평균)
- **출처**: J. F. C. Kingman, "The single server queue in heavy traffic", 1961 · H. Sakasegawa, *Annals of the Institute of Statistical Mathematics* 29, 1977 · *Factory Physics* 3판 8장 (쪽수 확인 필요) · [FabTime 사이클타임·대기행렬 공식](https://inficon.com/media/11486/download/FabTimeCycleTimeTutorialAndQueueingFormulasfromFabTimeWebsite.pdf)
- **가정**: 정상 상태, u < 1. 근사식이라 u가 0.7~0.9일 때 잘 맞고 낮을수록 부정확
- **변동계수**: fixed = 0, exponential = 1, 삼각분포 [a, b, c]는 `triangular_cv` (분산 = (a²+b²+c²−ab−ac−bc)/18). photo [16, 20, 27]이면 약 0.11
- **우리 공장에서의 값**: 도착이 일정(c_a = 0)하고 처리시간 변동도 작아서 대기가 거의 없다. photo 예상 0.9분 / 시뮬레이션 0.1분
- **시뮬레이션과 비교**: 무작위성이 큰 경우(exponential, u = 0.7~0.9)는 테스트에서 25% 이내로 맞는다. 우리 공장처럼 변동이 아주 작으면 근사식이 과대평가한다
- **알게 된 것**: 대기는 가동률만이 아니라 **변동**의 제곱에 비례한다. 같은 87.5% 가동률이라도 도착·처리가 exponential이면 photo 대기는 이론상 약 147분(1 × 0.875/0.125 × 21)이다. 가동률 90%→99%면 u/(1−u)가 9→99로 11배가 된다. 그래서 공장은 일부러 가동률 100%를 피한다
- **코드**: `expected_wait`, `triangular_cv`
