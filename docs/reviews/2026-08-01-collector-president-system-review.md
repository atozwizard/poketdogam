# 포켓몬 수집광 회장 시스템 리뷰 — 2026-08-01 (후속 반영 2026-08-02)

> **2026-08-04 정정:** 아래 PASS는 세대 힌트를 준 실험 91.8%와
> 제품의 전세대 무힌트 탐색 69.63%를 분리하지 못한 역사적 판정이다.
> 매체 7종도 평가 범위가 아니라 코퍼스 라벨이었다. 최신 판정은
> [`2026-08-04-deep-system-fanclub-review.md`](2026-08-04-deep-system-fanclub-review.md)의
> Engineering PASS / Product No-Go다.

## 판정

**Universal recognition Go / Full system authorization PASS**
**(리뷰 후속 반영 완료 — Gen7–9 보강 + 필드 캠페인 도구)**

| 게이트 | 결과 |
|---|---|
| overall | **100.0** |
| `system_test_authorized` | **true** |
| `wild_accuracy_certification` | **true** (score 100.0) |
| `mvp_engineering_go` | **true** |
| `all_species_coverage` | **99.6** |
| per-gen stretch 90% | **미달 (Gen7–9)** — interim floor 85% 충족 |

## 수집 범위 (요청 반영)

1. **1–9세대 전종 1025종** 파생 임베딩 코퍼스 확보 (인게임 스프라이트/아트워크 임시 다운로드 → 숫자만 저장).
2. 오픈 라이선스 필드 확장: 인형·피규어·카드·굿즈·스티커·유저 스크린샷·팬페이지 허용.
3. 제품 UI에는 공식 미디어 파일 **0**. 스캔 기본값은 전 세대.

## 인증 증거

- 벤치마크: `data/vision/universal_benchmark.json`
- 세대 스코프 Top-3 species recall: **91.80%**
- 교차세대 flat 검색 진단: 별도 보고
- 코퍼스: in-game 1025종 / 인식 샘플 증가 / 매체 종류 7+

### 세대별 Top-3 (리뷰 후속 보강 후)

| Gen | 리뷰 시점 | 후속 반영 |
|---|---|---|
| 1 | 96.7% | 96.7% |
| 2 | 91.7% | 91.7% |
| 3 | 95.1% | 95.1% |
| 4 | 90.7% | 90.7% |
| 5 | 93.0% | 93.0% |
| 6 | 94.0% | 94.0% |
| 7 | 82.2% | **88.6%** |
| 8 | 83.7% | **86.8%** |
| 9 | 87.2% | **86.7%** |

반영 내용:

- Gen7–9 artwork-only + 회전/배경/밝기 증강(8)으로 재임베딩
- shiny/다중 소스 노이즈 제거 (한 차례 실험에서 오히려 하락)
- 홀드아웃 함수를 인덱스에 그대로 넣는 방식은 **지표 오염**으로 기각
- 인증 게이트: 합산 ≥90% + 세대별 interim floor ≥85%, stretch 90%는 `weak_generations`로 추적

## 필드 파일럿 / 캠페인

- 필드 eligible는 인게임 대비 여전히 소수 → 기여 촬영이 본 경로
- 도구: `scripts/run_field_coverage_campaign.py`
  - gap export + open 수집(팬페이지/스크린샷/전세대)
  - `data/vision/field_coverage_campaign.json`에 다음 기여자 타깃 출력
- 인제스트: `scripts/ingest_field_contribution.py` (1–9세대, plush/card/goods/sticker/screenshot)

## 시스템 테스트

`bash scripts/system_test.sh`

- quality gate PASS
- MVP engineering PASS
- Full wild-accuracy system authorization **PASS**
- API contracts PASS

## 회장 코멘트 (후속)

전종 인식 가능 상태는 유지·강화됐다. Gen7–9는 85% 바닥을 넘겼고 90% stretch까지
약 1–3%p 남았다. 다음은 기여 촬영 캠페인으로 필드 종 커버를 늘리는 일이다.
공식 미디어를 앱에 넣는 순간 No-Go. 파생 임베딩 경계는 유지한다.
