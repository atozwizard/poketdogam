# 포켓덱스 구현 계획서 (무료·온디바이스 재편)

## 0. 계획 목적
- 유료 클라우드 LLM/OCR·상시 서버 인스턴스 없이 MVP를 구현한다.
- **Dex 자료 확보**와 **OCR 매칭**은 분리하지 않고 **Local Scan Core** 단일 트랙으로 진행한다.
- 기준 문서:
  - `온디바이스_무료티어_계획.md` (DB/동접/Supabase 결정 포함)
  - `prod_단계별_작업계획.md` (prod까지의 단계별 실행 계획)

## 공통 원칙
- 핫패스 = 온디바이스 SQLite. Supabase는 스캔/도감에 사용하지 않는다.
- 상시 API 인스턴스 없음. Dex는 PC/CI 배치 빌드만.
- `uv` + 단독 실행 가능한 `.py` 유지.
- 변경은 `docs/logs` / `docs/rules` 준수.

## Phase 1–2. 부트스트랩 / uv
- 저장소 구조·`pyproject.toml`·`uv sync` 재현.

## Phase 3. Local Scan Core (병합: Dex + Alias + Matcher + OCR fixture)
- 목표: 오프라인 카드 식별의 데이터·매칭 축을 한 번에 완성.
- 작업:
  1. `scripts/build_local_dex/` — PokéAPI fetch/cache → normalize → aliases → type_chart → `dex.sqlite`
  2. fuzzy matcher (exact → fuzzy → Top-3)
  3. OCR 문자열 fixture + (가능 시) 이미지 fixture 디렉터리
  4. OS OCR 어댑터 스펙/PoC 입력으로 matcher 연결
- 완료 기준 (단일 DoD):
  - Gen1–9 적재, `dex.meta.json` 존재, 텍스트 DB ≤ 15MB
  - 한글 fixture `match@3 ≥ 0.9`
  - **Supabase/서버 인스턴스 없이** 재현

## Phase 4. Android 클라이언트 (카메라·패키징)
- 목표: Android 우선 패키징으로 실기기 스캔.
- 작업:
  - 실기기 연결 전 FastAPI 내장 웹 UI로 Rotom Dex OS UX 완료
  - CameraX **스틸 캡처**(실시간 OCR 비목표)
  - ML Kit OCR → 공유 matcher → Top-3
  - `dex.sqlite` assets/첫 다운로드 후 읽기 전용 오픈
  - APK 용량 예산, minSdk/ABI(`arm64-v8a`) 고정
- 완료 기준: 실기기 1종 이상에서 스캔→Top-3→상세(로컬)
- 스택: **Kotlin + Jetpack 확정**. Flutter는 iOS 검토 시점에 재논의.

## Phase 5. 실카드 OCR 게이트
- 30→100장 벤치. 미달 시 PP-OCR 보강 또는 언어 범위 축소.

## Phase 6. UX 완결 (템플릿 응답·상세·로컬 컬렉션)
- LLM 없이도 스캔→상세→진화/상성→저장.
- 로컬 Ollama 등 로컬 LLM이 있으면 답변 문장화에 사용하고, 실패 시 템플릿으로 degrade.
- UI에는 현재 runtime(`ollama`/`template`/`fallback_template`)을 표시.

## Phase 7. 온디바이스 1B (옵션)
- 문장화만. 미설치 시 템플릿 degrade.
- 기본 개발/검증 모델은 `llama3.2:1b`로 둔다. 더 큰 Ollama 모델은 프롬프트 실험용으로만 사용하고 prod 기본값으로 두지 않는다.
- 호스팅: 상시 인스턴스 불필요. 초기 HF 등 공개 URL 또는 사이드로드 → 배포 시 Cloudflare R2.
- MVP 초기는 1B 없이 템플릿만으로도 DoD 통과.
- STS/TTS는 YouTube/공식 캐릭터 음성 추출이 아니라 허가 음성 또는 공개 라이선스 음성으로만 별도 prototype 진행.

## Phase 8. 선택 클라우드 (콜드패스)
- Cloudflare: `dex.sqlite` 스냅샷 배포만 우선.
- Supabase: **계정/컬렉션 sync만** 후순위. 스캔 쿼리 금지.
- 없어도 앱 완결이어야 함.

## Phase 9–10. 품질 로그 / 릴리즈
- OCR 엔진·match score·dataset_version 로컬 기록.
- 유료 API·상시 인스턴스 의존 0으로 베타. iOS는 Android 게이트 후.

## 즉시 실행 백로그
1. 실기기 연결 전 Rotom Dex OS 웹 UI 완성 (`/`, `/v1/scan/text`)
2. Local Scan Core 전체 Dex 확장 (`build_local_dex` + matcher + fixture 30장)
3. Android Kotlin + Compose UI 포팅
4. CameraX 셔터 + ML Kit OCR 실기기 연결
5. 핫패스에 Supabase/인스턴스 넣지 않기. 1B 스토리지는 급하지 않음(템플릿 우선)

## DB·동접·SQLite 요약 (계획 고정)
| 질문 | 답 |
| --- | --- |
| Supabase? | 도감/OCR 주 DB **아니오**. sync만 후순위. |
| 동접? | 핫패스=기기 SQLite → 공유 동접 없음. |
| 인스턴스? | **없음**. |
| 기기에서 sqlite 빌드? | **안 함**. CI가 빌드, 기기는 읽기. |

## 변경 이력

| 수정일자 | 수정자 | 변경 대상 문서 | 수정 요약 | 반영 상태 |
| :-- | :-- | :-- | :-- | :-- |
| 2026-07-28 19:45 +09:00 | Codex | `docs/specs/implementation_plan_phase10.md` | 로컬 Ollama 문장화 옵션과 합법 STS/TTS 원칙 반영 | 완료 |
| 2026-07-28 19:20 +09:00 | Codex | `docs/specs/implementation_plan_phase10.md` | prod 단계별 계획 문서 연결 및 실기기 전 Rotom Dex OS UI 게이트 추가 | 완료 |
| 2026-07-28 09:21 +09:00 | Cursor | `docs/specs/implementation_plan_phase10.md` | Kotlin 확정. 1B는 R2/HF 파일 배포, 인스턴스 불필요 | 완료 |
| 2026-07-27 18:23 +09:00 | Cursor | `docs/specs/implementation_plan_phase10.md` | Android 우선·CameraX 셔터 Phase 추가. CI빌드/기기읽기 SQLite 명시 | 완료 |
| 2026-07-27 17:45 +09:00 | Cursor | `docs/specs/implementation_plan_phase10.md` | Phase 3–5를 Local Scan Core로 병합. Supabase=sync 전용, 인스턴스 없음 명시 | 완료 |
| 2026-07-27 16:59 +09:00 | Cursor | `docs/specs/implementation_plan_phase10.md` | LiteLLM/Solar 중심 Phase를 Dex 빌드·OCR 매칭·온디바이스 1B 중심으로 재편 | 대체됨 |
