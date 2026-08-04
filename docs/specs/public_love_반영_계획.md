# 대중 사랑(Public Love) 반영 계획·명세

근거: [`docs/reviews/2026-08-03-korean-fanclub-president-public-love.md`](../reviews/2026-08-03-korean-fanclub-president-public-love.md)

작성일: 2026-08-03
수정일: 2026-08-04
역할: 한국 포켓몬 팬클럽 회장 리뷰(#4)를 **실행 가능한 단계·게이트·산출물**로 고정한다.

---

## 0. 목적

세대 힌트 파생 실험을 회귀 기준으로 **유지**하면서, 제품과 동일한
전세대 무힌트 탐색·실물·한국어 근거를 인증 수준으로 끌어올린다.

한 줄: **뼈대(전종 파생 실험)는 있지만, 제품 인증·실물·한국어·신뢰는 아직 미완성이다.**

---

## 1. 완료 정의 (Public Love DoD)

아래를 **동시** 충족하면 “사랑받기 1차 목표” 달성으로 판정한다.

| ID | 조건 | 측정 |
|---|---|---|
| PL-D1 | 제품 공개 탐색 인증 | 세대 힌트 없이 1–9세대 평가, `certified=true`, Top-3≥90%, 실제 평가 media kinds≥4 |
| PL-D2 | 필드 인기 코어 커버 | eligible 필드 종 ≥ **150**, 크리에이터 ≥ **30**, 샘플 ≥ **300** |
| PL-D3 | Gen7–9 stretch | `per_generation_stretch_met=true` (각 세대 Top-3 ≥ 0.90, 오염 없는 벤치) |
| PL-D4 | 한글 카드 알파 | 실물 한글 카드 ≥30장, `match_recall@3 ≥ 0.90` (`fixtures/ocr/` + `benchmark_image_ocr.py`) |
| PL-D5 | 신뢰 카피 | UI/품질보드에 **제품 무힌트 vs 세대 힌트 실험 vs 실물 Field** 3개를 분리 표기 |
| PL-D6 | 프라이버시·라이선스 | 원본 미저장 배지, EXIF 제거, 공식 미디어 UI **0**, 엔지니어링 통합 PASS |
| PL-D7 | 컬렉션 애착 MVP | 세대별 수집률 + 확정 전 저장 잠금 유지 (공유는 공식 아트 없이 이름·세대 뱃지만) |

**2차(Love+)**: 한글 카드 100장 `match_recall@3 ≥ 0.95`, 필드 종 ≥453, Field fused Top-3를 별도 공개 게이트로 승격.

`system_test_authorized` 제품 승인은 Public Love DoD와 별도의 엄격한
Production 게이트다. 제품 무힌트 인증과 필드 151종·453장·30 creators·
Top-3 90% 조건을 모두 충족하기 전에는 `false`를 유지한다.

---

## 2. 비목표·가드레일

- 공식 스프라이트/아트워크를 제품 UI에 **전시하지 않는다**.
- 제품 무힌트, 세대 힌트 실험, Field fused Top-3를 **합쳐 마케팅 문구로 쓰지 않는다**.
- Gen7–9 stretch를 위해 홀드아웃과 **동일한 변환만** 넣은 증강으로 점수를 부풀리지 않는다.
- Openverse/Wikimedia 단독으로 1025종 실물 커버를 “완료”라고 선언하지 않는다. 기여자 촬영이 필수다.
- Production 라이선스 승인 전 스토어 배포 금지 (기존 prod 계획과 동일).

---

## 3. 베이스라인 (2026-08-04 정정)

| 지표 | 현재 | 1차 목표 |
|---|---|---|
| 제품 전세대 무힌트 Top-3 | 69.63% | ≥90% |
| 세대 힌트 파생 실험 Top-3 | 91.80% | 회귀 기준 유지(제품 인증 아님) |
| 실제 평가/코퍼스 라벨 매체 | 1종 / 7종 | 실제 평가 ≥4종 |
| Gen7 / 8 / 9 | 88.6 / 86.8 / 86.7% | 각 ≥90% |
| 필드 eligible | 91장 / 28종 / 20 creators | 300장 / 150종 / 30 creators |
| 필드 제품 경로 Top-3 | 9.89% | ≥90%(충분한 커버리지 포함) |
| 한글 카드 벤치 | fixture·게이트 경로 존재, 실물 30/100 규모는 미완 | 30장@90% → 100장@95% |
| 시스템 테스트 | 엔지니어링 통합 PASS / 제품 승인 HOLD | 전 DoD 충족 후 제품 승인 PASS |
| 컬렉션 UX | 목록·필터·저장·세대별 진행률·개별 삭제 | Phase A 유지; 공유는 Phase B |

산출물 참조:

- `data/vision/universal_recognition_cert.json`
- `data/vision/field_coverage_gap.{json,csv}`
- `data/vision/field_coverage_campaign.json`
- `scripts/system_test.sh` / `scripts/evaluate_quality_score.py`

---

## 4. 작업 스트림 (리뷰 #1–#10 ↔ 명세)

각 스트림은 **Owner 산출물 / Acceptance / 스크립트·경로**를 가진다.

### L1. 실물·스크린샷 커버 (“내 선반”)

| 항목 | 명세 |
|---|---|
| 목표 | 인기 코어 150종부터 카드·인형·굿즈·스티커·유저 스크린샷 eligible 확보 |
| 우선 타깃 | 피카츄·이브이·스타터 라인·전설/환상·세대별 대표 마스코트 (캠페인 JSON의 weekly top-10) |
| 작업 | 1) `export_field_coverage_gap.py`로 갭 갱신 2) `run_field_coverage_campaign.py`로 주간 타깃 10종 3) open collect (`--allow-fan-pages --allow-screenshots --all-generations`) 4) `review_field_photo_manifest.py` → `promote_field_contributions.py` 5) `build_physical_field_index.py` + `benchmark_field_photos.py` |
| Acceptance | 종≥150, samples≥300, creators≥30; gap CSV에 “covered_core” 플래그 |
| 산출물 | `field_coverage_campaign.json`, promoted manifest, field benchmark JSON |

### L2. 한글 카드 OCR

| 항목 | 명세 |
|---|---|
| 목표 | 한글 이름 한 번에 Top-3 안착 |
| 알파 | 실물 30장, `match_recall@3 ≥ 0.90` |
| MVP | 실물 100장, `match_recall@3 ≥ 0.95` (기존 `MVP_기능_명세서`·`prod_단계별_작업계획` P2와 정렬) |
| 작업 | 1) `fixtures/ocr/korean_cards.jsonl` 메타(조명·흐림·언어) 보강 2) name-band crop UX 회귀 3) alias(피카추/피카츄 등) 실패 재분류 4) `benchmark_image_ocr.py` CI/로컬 게이트 |
| Acceptance | 벤치 리포트 + 품질보드 `card_name_band_*` true 유지 |
| 비고 | 텍스트 fixture만으로 알파 완료를 주장하지 않음 |

### L3. Gen7–9 stretch 90%

| 항목 | 명세 |
|---|---|
| 목표 | `per_generation_stretch_met=true` |
| 작업 | 1) Gen7–9 artwork-only 파생 재임베딩 2) 카메라형 증강(회전·배경·밝기) — holdout 복제 금지 3) `benchmark_universal_recognition.py` 재실행 4) cert 재발급 |
| Acceptance | Gen7/8/9 각각 species Top-3 ≥ 0.90; `gaps.per_generation_to_stretch` 비움 |
| 오염 금지 | 벤치 이미지와 동일 transform을 train/index에만 넣고 점수를 올리는 행위 금지 (2026-08-02 교훈) |

### L4. 프라이버시 기본값

| 항목 | 명세 |
|---|---|
| 유지 | 원본 미저장 배지, 세션 TTL 삭제, EXIF strip, 아동/코스프레 hard-reject |
| Acceptance | `evaluate_quality_score` 프라이버시 체크 + system_test PASS |
| 회귀 | UI 문구에서 “클라우드 업로드” 암시 금지 |

### L5. 로토무 카피·실패 팁

| 항목 | 명세 |
|---|---|
| Done | 스캔 카피에 1–9세대·카드·인형·굿즈·스크린샷 명시 |
| Done | low_confidence/error 시 조명 / 70% 점유 / 카드명 밴드 / 배경 단순화 복구 팁 |
| Acceptance | `app/ui`에 실패 상태별 tip 문자열 ≥3; 단위 테스트 또는 UI contract에 needle 포함 |

### L6. 확인 UI (자동 확정 금지)

| 항목 | 명세 |
|---|---|
| 유지 | Top-3 선택 전 저장·낭독 잠금; ranking score ≠ 확률 고지 |
| Acceptance | `ranking_score_is_not_probability`, confirmed-before-save 게이트 true |

### L7. 컬렉션·자랑·공유

| 항목 | 명세 |
|---|---|
| Phase A | **완료** — 저장 탭에 세대별 수집률(보유 종 / 세대 종수), 진행 바, 개별 삭제 |
| Phase B | 공유 카드: 한글 이름 + 세대 뱃지 + 수집 수 — **공식 아트·스프라이트 없음** |
| 데이터 | 로컬 `localStorage` 컬렉션 + dex 세대 맵 (서버 업로드 없음) |
| Acceptance | 360px에서 세대 진행률 가독; 공유 이미지에 공식 미디어 0 |

### L8. 커뮤니티 기여 루프

| 항목 | 명세 |
|---|---|
| 운영 리듬 | 매주 월요: gap export → campaign top-10 → 기여자 공지 템플릿 |
| 도구 | `ingest_field_contribution.py`, `batch_ingest_field_contributions.py`, gap CSV |
| Acceptance | `field_coverage_campaign.json`에 `week`, `targets[10]`, `media_kinds`, `howto` 필드 |
| KPI | 주당 신규 eligible ≥15장 또는 신규 종 ≥5 |

### L9. 신뢰 표기 (Universal ≠ Field)

| 항목 | 명세 |
|---|---|
| UI | **완료** — 제품 무힌트 69.6%, 세대 힌트 실험 91.8%, 실물 파일럿 9.9%를 분리 |
| 품질보드 | **완료** — product open / generation-aided lab / field pilot을 별 키로 유지 |
| 문서 | 리뷰·로그·마케팅 초안에서 Field를 Universal 점수로 대체 금지 |
| Acceptance | UI contract needle: `파생` + `실물` (또는 동등 분리 문구); cert JSON `field_pilot` 유지 |

### L10. 접근성·모바일

| 항목 | 명세 |
|---|---|
| 유지 | 360px, 터치 타깃, 저조도 안내, Android 카드명 밴드 |
| Next | 중급 Android 실기기 체크리스트 1회 통과 (CameraX → Top-3 → 저장) |
| Acceptance | `mobile_touch_target`, Android lint/test APK 게이트; 실기기 체크 로그 1건 |

---

## 5. 단계별 일정 (PL0–PL4)

일정은 **달력 주(week)** 단위. 시작점: 2026-08-03.

### PL0 — Now (기반 통합 완료·제품 인증 미완) · Week 0

- [x] 세대 힌트 파생 회귀 91.8% + 엔지니어링 시스템 통합 PASS
- [ ] 제품 무힌트 공개 탐색 인증(69.63% → 90%)
- [x] 스캔 카피 전세대·전매체 명시
- [x] 팬클럽 리뷰 문서
- [x] 신뢰 근거 3분법 UI·실패 팁·세대별 수집률
- **게이트**: `bash scripts/system_test.sh` 엔지니어링 PASS; `system_test_authorized` 제품 승인은 HOLD
- **회귀 주기**: 인식/수집 변경마다 system_test

### PL1 — Field Core 150 · Week 1–4

| Day/Week | 작업 |
|---|---|
| W1 | 인기 150종 리스트 고정 → campaign JSON; open+기여 인제스트 집중 |
| W2–3 | review/promote 루프; creators≥30 목표 |
| W4 | field index 재빌드 + field bench 스냅샷; UI에 실물 커버 종수 표기(L9) |

**Exit gate**

- eligible species ≥150, samples ≥300, creators ≥30
- 제품 무힌트 인증 PASS + 세대 힌트 회귀 후퇴 없음
- L9 분리 카피 머지

### PL2 — Gen7–9 Stretch · Week 2–5 (PL1과 병렬 가능)

| 작업 | 상세 |
|---|---|
| 재임베딩 | Gen7–9 artwork-only + 정직한 aug |
| 벤치 | `benchmark_universal_recognition.py` → 제품 무힌트 cert와 세대 힌트 lab 결과를 각각 갱신 |
| 문서 | `PO_95_품질게이트.md`에 stretch 달성 재판정 |

**Exit gate**: `per_generation_stretch_met=true`, weak_generations 비움

### PL3 — 한글 카드 알파·실패 팁 · Week 3–6

| 작업 | 상세 |
|---|---|
| 벤치 | 실물 한글 30장 메타+이미지 (Git LFS 또는 로컬-only + CI stub) |
| UX | L5 실패 팁 3종 |
| 게이트 | `match_recall@3 ≥ 0.90`; name-band 체크 유지 |

**Exit gate**: PL-D4 + L5 Acceptance

### PL4 — 컬렉션 애착 + Love 판정 · Week 5–8

| 작업 | 상세 |
|---|---|
| UX | L7 Phase A 세대별 진행률; Phase B 공유(선택) |
| 한글 MVP | 100장@95% 착수 (미달 시 Love+로 이월, 1차 DoD는 알파로 충족 가능) |
| 실기기 | L10 Android 체크 로그 |
| 판정 | PL-D1–D7 체크리스트 사인오프 → `docs/reviews/YYYY-MM-DD-public-love-signoff.md` |

**Exit gate**: Public Love DoD 1차 전부 true. `system_test_authorized`는 별도
Production 게이트로 평가하며 미달이면 HOLD를 유지한다.

---

## 6. 메트릭·산출물 맵

| 메트릭 | 소스 | 갱신 주기 |
|---|---|---|
| 제품 무힌트 Top-3 / 세대 힌트 per-gen | `universal_recognition_cert.json` | 임베딩·벤치 변경 시 |
| Field species/samples/creators | cert `field_pilot` + field manifest | 주 1회 캠페인 후 |
| Field gap | `field_coverage_gap.json` | 주 1회 |
| 한글 OCR@3 | OCR bench report | 벤치 추가 시 |
| Quality scoreboard | `evaluate_quality_score.py` | system_test |
| UI contracts | system_test / TestClient needles | UI 변경 시 |

필수 커맨드 치트시트:

```bash
# 인증·시스템
bash scripts/system_test.sh
uv run python scripts/evaluate_quality_score.py

# 필드 캠페인
uv run python scripts/export_field_coverage_gap.py
uv run python scripts/run_field_coverage_campaign.py
# (선택, 느림) ... --species-search

# Universal 재인증
uv run python scripts/benchmark_universal_recognition.py
# (프로젝트 관례에 따른 cert 기록 스크립트)

# 한글 OCR
uv run python scripts/benchmark_image_ocr.py --fixtures fixtures/ocr/korean_cards.jsonl
```

---

## 7. 주간 운영 리듬 (팬클럽 운영 = 제품 성장)

| 요일 | 액션 | 산출 |
|---|---|---|
| 월 | gap export + campaign top-10 | `field_coverage_campaign.json` |
| 화–목 | open collect / 기여 인제스트 / review | pending → eligible |
| 금 | promote + field bench 스냅샷; Universal 회귀(변경 시) | bench JSON |
| 토–일 | (선택) 한글 카드 촬영·메타 기입 | fixtures 증분 |

공지 템플릿(요약):

> 이번 주 타깃 10종: {list}. 허용: 카드·인형·굿즈·스티커·게임 스크린샷. 금지: 아동 식별·무단 공식 아트 재배포. 촬영 시 배경 단순·이름 보이게.

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| Open 라이선스만으로 150종 미달 | 기여자 이벤트 + 인기종 우선; 완료 선언을 코어 150에 한정 |
| Gen7–9 stretch 정체 | 오염 없는 aug 다양화; 세대별 실패 종 리스트 우선 보강 |
| 한글 카드 실물 수급 | 알파 30을 PL3 필수, 100은 Love+; 라이선스·개인정보 체크리스트 |
| Field 정확도 과대 광고 | L9 강제; Field Top-3는 별 게이트 전까지 “파일럿”만 표기 |
| Dex/임베딩 용량 | `validate_dex` 96MB 상한 모니터링; 세대별 증분 빌드 |

---

## 9. 추적 체크리스트 (사인오프용)

### 인증·수집 (요청 1–3)

- [x] 1–9세대 1025종 파생 코퍼스·세대 힌트 회귀 유지
- [ ] 제품 무힌트 Top-3≥90% + 실제 평가 media kinds≥4
- [ ] Gen7–9 세대 힌트 stretch 90%; 제품 인증과는 별도

### 수집광 시스템 테스트 (요청 3)

- [x] `bash scripts/system_test.sh` 엔지니어링 통합 PASS
- [x] 스캔 UI에 전세대·전매체·공식 미디어 미포함
- [x] 한글 인기종 검색→선택→저장→세대 진행률→삭제 브라우저 스모크
- [x] 360px 가로 넘침 없음
- [x] 리뷰 메모: `docs/reviews/2026-08-04-deep-system-fanclub-review.md`

### 팬클럽·대중 사랑 (요청 4–5)

- [x] 필요 요소 파악 문서
- [x] 본 계획·명세 (`docs/specs/public_love_반영_계획.md`)
- [ ] PL1–PL4 Exit gate 순차 통과
- [ ] Public Love DoD 1차 사인오프 문서

---

## 10. 문서 관계

| 문서 | 역할 |
|---|---|
| `docs/reviews/2026-08-03-korean-fanclub-president-public-love.md` | Why / 우선순위 |
| **본 문서** | What / When / Gate |
| `docs/specs/PO_95_품질게이트.md` | 품질 점수·분리 게이트 |
| `docs/specs/prod_단계별_작업계획.md` | Prod/Android/OCR 장기 계획 (한글 30/100과 정렬) |
| `docs/specs/MVP_기능_명세서.md` | MVP 수용 기준 |

변경 규칙: 게이트 숫자(150종, 90%, 30장 등)를 바꿀 때는 본 문서 §1·§5와 리뷰 문서를 **같은 PR**에서 갱신한다.

## 11. 변경 이력

| 수정일자 | 수정자 | 수정 요약 | 반영 상태 |
| :-- | :-- | :-- | :-- |
| 2026-08-04 09:45 +09:00 | Codex | 제품 무힌트/세대 힌트 실험/필드 증거 분리, L5·L7 Phase A·L9 반영, 제품 승인 HOLD로 정정 | 완료 |
