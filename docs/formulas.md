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

TODO(명민)

## 2. 병목 판정

TODO(명민)

## 3. 공장 최대 생산량

TODO(명민)

## 4. 장비 가동률

TODO(명민)

## 5. Little's Law

TODO(명민)

## 6. 대기시간 근사

TODO(명민)
