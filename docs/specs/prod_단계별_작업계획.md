# 포켓덱스 Prod 단계별 작업 계획

## 0. 목적
- 2026-07-28 기준 구현 상태에서 production 릴리즈까지 필요한 작업을 단계별로 고정한다.
- MVP 핫패스는 로컬 SQLite Dex, OS OCR, fuzzy matcher, 템플릿 응답으로 완결한다.
- UI는 **로토무 모티프의 Rotom Dex OS**로 통일한다.
- 실기기 연결 전에는 FastAPI 내장 웹 UI로 전체 UX 플로우를 검증하고, 이후 Android Kotlin + Jetpack UI로 포팅한다.

## 1. Prod 완료 정의
- 유료 클라우드 LLM/OCR 없이 스캔, 후보 확인, 상세 조회, 템플릿 응답이 동작한다.
- `dex.sqlite`는 Gen1-9 범위로 재현 빌드되고 `dex.meta.json`과 함께 버전 관리된다.
- 실물 한국어 카드 30장 알파 `match_recall@3 >= 0.90`, 100장 MVP `>= 0.95`를 통과한다.
- Android 실기기 1종 이상에서 CameraX 스틸 캡처, ML Kit OCR, 로컬 matcher, 상세 화면이 오프라인으로 이어진다.
- 로토무 모티프 UI는 첫 화면부터 스캔, 후보, 상세, 대화, 수동 검색 상태까지 완성되어 있다.
- Supabase는 스캔/도감 핫패스에 쓰지 않는다. Cloudflare/R2는 Dex snapshot 배포용 콜드패스만 허용한다.
- PoC는 간접 사실 데이터만 사용하고, 정식 제품 라이선스 승인 전 Production 배포를 금지한다.

## 2. 단계별 계획

### P0. 기준선 정리와 실기기 전 UI 완성
- 작업:
  1. FastAPI 루트(`/`)에서 Rotom Dex OS 웹 UI 제공.
  2. `/v1/scan/text` fixture 스캔 API 제공.
  3. `/v1/scan`은 실제 이미지 OCR만 허용하고 파일명 fallback을 금지한다.
  4. 스캔 입력, Top-3 후보, 상세 패널, 근거 템플릿 대화, 로컬 저장 UI를 한 화면에서 완료.
  5. UI 상태를 `idle`, `scanning`, `locked`, `low_confidence`, `error`로 분리.
  6. 실제 이미지 OCR과 개발용 matcher 지표를 분리한다.
  7. `/v1/chat/stream` SSE를 우선 사용해 답변 말풍선을 점진 갱신한다.
  8. 360px 모바일 viewport, keyboard focus, reduced-motion을 검증한다.
- 산출물:
  - `app/ui/index.html`
  - `app/ui/styles.css`
  - `app/ui/app.js`
  - `/v1/scan/text`
  - `/v1/chat` runtime metadata
  - `/v1/chat/stream` SSE
  - `/v1/voice/status`
  - `/v1/voice/preview`
- 게이트:
  - 브라우저에서 `/` 진입 가능.
  - fixture 텍스트 `피카추 HP 60` 입력 시 피카츄 후보 반환.
  - 도감 상세와 대화 응답이 같은 `dex.sqlite` 기준으로 표시.
  - 로컬 Ollama 실패 시 템플릿 fallback이 표시된다.
  - UI 채팅 배지에 `ollama · llama3.2:1b` 또는 fallback runtime이 표시된다.
  - Voice Core는 실 STS로 오인되지 않고 `pre_device_preview` 상태와 독자 AI 보이스 정책을 표시한다.

### P1. Local Scan Core 전체 Dex 빌드
- 작업:
  1. `fetch_pokeapi.py`로 Gen1-9 PokéAPI raw cache 확보.
  2. `normalize_dex.py`를 seed 입력에서 raw cache 입력까지 확장.
  3. 종, 폼, 타입, 스탯, 진화, 다국어 이름을 SQLite로 export.
  4. `name_aliases`에 OCR용 한글/영문/일문 alias와 흔한 오타를 추가.
  5. `validate_dex.py`에 고아 FK, alias 중복, 필수 이름 누락, 타입 상성 18x18 검증을 강화.
- 산출물:
  - Gen1-9 `data/dex.sqlite`
  - `data/dex.meta.json`
  - raw cache 디렉터리 또는 CI artifact
- 게이트:
  - `species_count >= 1025`
  - 텍스트 DB 용량 `<= 15MB`
  - fixture `match_recall@3 >= 0.90`

### P2. OCR 벤치 30장 게이트
- 작업:
  1. 한국어 카드 30장 fixture를 `fixtures/ocr/`에 추가.
  2. OCR raw text, 정답 pokemon_id/form_id, 언어, 조명/흐림 조건을 기록.
  3. match@1, match@3, low-confidence 비율, 평균 latency를 산출.
  4. 실패 케이스를 alias, crop UX, matcher threshold로 재분류.
- 게이트:
  - 한국어 `match_recall@3 >= 0.90`
  - Top-1이 낮아도 Top-3 확인 UX로 복구 가능.
  - 텍스트/합성 이미지 30건은 파이프라인 회귀로만 기록하고 P2 완료 근거로 사용하지 않음.

### P3. Android UI 포팅
- 작업:
  1. Kotlin + Jetpack Compose 프로젝트를 추가한다.
  2. Rotom Dex OS 화면 구조를 웹 UI와 동일하게 구성한다.
  3. 화면: 홈/스캔, 후보 확인, 상세, 대화, 수동 검색, 설정.
  4. `dex.sqlite` assets 복사와 read-only open 흐름을 구현한다.
  5. Python matcher와 동일한 normalize/fuzzy 규칙을 Kotlin으로 포팅한다.
- 게이트:
  - 에뮬레이터에서 fixture OCR 텍스트 입력으로 Top-3와 상세 화면 표시.
  - 네트워크 비활성 상태에서도 도감 상세 조회.

### P4. Android CameraX + ML Kit 연결
- 작업:
  1. CameraX 스틸 캡처를 연결한다.
  2. ML Kit Text Recognition으로 OCR text를 생성한다.
  3. OCR 결과를 로컬 matcher에 전달한다.
  4. 저신뢰 결과는 Top-3 확인 또는 수동 검색으로 보낸다.
- 게이트:
  - 실기기 1종에서 스캔 -> OCR -> Top-3 -> 상세.
  - 스캔 핫패스에서 원격 API 호출 0회.

### P5. OCR 벤치 100장과 UX 보강
- 작업:
  1. 카드 100장으로 벤치 확장.
  2. 실패 케이스를 언어, 반사, 기울기, 폰트, 카드명 위치로 분류.
  3. 재촬영 프레임, 카드명 영역 crop, 수동 검색 UX를 보강.
  4. 필요 시 PP-OCR tiny/lite를 옵션 다운로드로 검토한다.
- 게이트:
  - 한국어 `match_recall@3 >= 0.90`
  - P95 latency가 사용자가 기다릴 수 있는 범위로 유지.

### P6. 로컬 컬렉션과 품질 로그
- 작업:
  1. 확정한 후보를 로컬 컬렉션에 저장한다.
  2. `ocr_engine`, `match_score`, `dataset_version`, latency, confirmation 여부를 로컬 품질 로그에 기록한다.
  3. Supabase sync는 feature flag 뒤의 후순위로 둔다.
- 게이트:
  - 오프라인 상태에서 컬렉션 저장/조회.
  - 로그에 개인 이미지 원본을 저장하지 않음.

### P6.5. 합법 음성 Cascaded STS/TTS Prototype (제품 메인)
- 기준 문서: `docs/specs/음성_STS_실시간대화_및_Omni2실험_계획.md`
- 작업:
  1. YouTube/공식 캐릭터 음성 추출은 제외한다.
  2. 직접 녹음, 허가받은 음성, 공개 라이선스 음성, 또는 공식 음색을 모방하지 않는 독자 AI 합성 음성으로 “전기 디바이스 보이스” 샘플셋을 만든다.
  3. **Cascaded** 로컬 STT → Rotom/Dex/LLM → style TTS 흐름을 PoC로 묶는다 (제품 메인).
  4. streaming STT/TTS + barge-in을 넣어 **턴제 실시간 대화**를 만든다 (Moshi급 full-duplex는 비목표).
  5. `voice_assets`에 source, permission, distribution_scope, model_version을 저장한다.
  6. emotion 태그 → Rotom 톤 → TTS style 매핑을 넣는다.
- 게이트:
  - 모든 음성 샘플에 사용 허락 또는 학습/배포 가능 라이선스가 있다.
  - 특정 공식 캐릭터/성우 음색 복제 목적의 모델이 없다.
  - 결과 음성은 공식 로토무/성우 음성과 혼동될 정도의 유사성을 목표로 하지 않는다.
  - 로컬 경로 TTFA ≤ 1.5s (중급 기기 목표), barge-in 시 TTS 중단.

### P6.6. Voice Lab — OpenS2S / Moshi / LLaMA-Omni2 실험 (옵트인 GPU)
- 기준 문서: `docs/specs/음성_STS_실시간대화_및_Omni2실험_계획.md`, `OpenS2S_감정STS_및_멀티턴메모리_서베이.md`
- 작업:
  1. **OpenS2S**: 감정 S2S 품질 상한 실험. transcript/emotion → Agent sidechannel.
  2. **Moshi**: ~200ms 풀듀플렉스 체감 데모. EN 주력, 폰 핫패스 금지.
  3. **LLaMA-Omni2-0.5B-Bilingual**: E0 추론 스모크 → E1 자체 KR Rotom 합성 데이터 → E2 Stage I(a) LoRA → E3 평가 → E4 옵트인 연결.
  4. Omni2는 **비상업/학술 격리**. 제품 배포 전 상업 라이선스 없으면 메인 경로에 넣지 않는다.
  5. Dex FACTS는 Omni2에 암기시키지 않고 Agent+SQLite로 유지.
  6. 실패 시 항상 Cascaded(P6.5)로 degrade.
- 게이트:
  - GPU 경로 feature flag OFF가 기본.
  - 라이선스·IP 혼동·FACTS 준수 Go/No-Go 통과 전에는 prod 빌드에 미포함.
  - 소형 STS 후보 표(Mini-Omni, UniSS, Hibiki 등)는 문서에 유지하되 Omni2만 우선 실험.

### P7. Dex 배포와 릴리즈 파이프라인
- 작업:
  1. CI에서 Dex 빌드, 검증, artifact 생성.
  2. Android 빌드는 검증된 `dex.sqlite`만 포함한다.
  3. 선택적으로 Cloudflare R2에 Dex snapshot과 manifest를 업로드한다.
  4. 앱 버전과 `dataset_version`을 분리한다.
- 게이트:
  - CI 실패 시 앱 빌드 중단.
  - 새 Dex가 없어도 기존 번들 Dex로 앱 기능 유지.

### P7.5. 1B LLM 프로파일 고정
- 작업:
  1. 기본 제품 프로파일은 `grounded_template`, `llama3.2:1b`는 명시적 옵트인으로 둔다.
  2. 프롬프트는 로컬 Dex FACTS를 입력받아 짧은 문장화만 하도록 제한한다.
  3. 모델 미설치, timeout, 빈 응답 시 `fallback_template`으로 내려간다.
  4. 20B 이상 모델은 프롬프트 실험/비교 벤치용으로만 사용한다.
  5. 개발 UI에서는 1B 응답을 SSE로 스트리밍해 토큰 도착감을 확인한다.
- 게이트:
  - UI에 `llm_runtime`과 `llm_model`이 표시된다.
  - 1B 모델로 3초 내외 응답이 가능하다.
  - FACTS 밖 환각을 줄이기 위해 템플릿 fallback이 유지된다.
  - 스트리밍이 실패해도 기존 완성형 `/v1/chat` 응답으로 degrade된다.

### P8. Production 릴리즈
- 작업:
  1. Play Internal Test.
  2. Closed Test.
  3. 개인정보, IP/이미지 재배포, 오픈소스 라이선스 점검.
  4. 네트워크 오프라인 QA.
  5. 릴리즈 노트와 롤백 절차 작성.
- 게이트:
  - 유료 API 키와 상시 서버 의존 0.
  - 실기기 스캔 성공률과 수동 복구 흐름 승인.

## 3. 현재 즉시 작업 순서
1. P0 실기기 전 UI 완성. **완료**
2. P1 PokéAPI 간접 사실 데이터 기반 전체 Dex 확장. **완료**
3. P2 실물 한국어 카드 30장 벤치. **미수행** (텍스트/합성 이미지 30건 회귀 통과)
4. P3 Android Compose UI 포팅. **소스 구현, 빌드 미검증**
5. P4 CameraX + bundled Korean ML Kit 연결. **소스 구현, 실기기 미검증**

## 4. 구현도 스냅샷 (2026-07-29 09:41 +09:00)

| 단계 | 상태 | 확인된 구현 | 남은 게이트 |
| :-- | :-- | :-- | :-- |
| P0 | 완료 | 실제 이미지 OCR, 업로드 보호, Top-3, 검색, 상세, grounded SSE 대화, 컬렉션, 데이터 삭제, 360px | 실제 사용자 사용성 평가 |
| P1 | 완료 | 1,025종, 1,351폼, 비기본 326폼, 진화 조건 550개, alias 5,576개, DB 9.15MB | 정기 데이터 갱신 |
| P2 | 미완료 | matcher 30/30, 합성 이미지 Vision→matcher 30/30·P95 343.62ms | 실물 카드 30장 조건별 실측 |
| P3–P4 | 소스 구현 | Compose, CameraX, bundled Korean ML Kit, read-only Dex, Top-3, 상세 | Android SDK 빌드·에뮬레이터·실기기 |
| P5 | 미착수 | 없음 | 실물 카드 100장, 중급 Android P95·recall@3 95% |
| P6 | 웹 PoC 완료 | 확정 게이트, 검색/즐겨찾기/내보내기/삭제, 비식별 trace, 세션 TTL 삭제 | Android 컬렉션 저장소 |
| P6.5 | 프리뷰 | browser speech synthesis와 정책 표시 | STT→Agent→TTS, streaming, barge-in, TTFA 실측 |
| P6.6 | 문서/설계 | 실험 계획과 안전·라이선스 게이트 | GPU 실험 E0 이후 |
| P7 | 부분 완료 | 웹 품질 CI, strict Dex validator, Android 검증 Dex 생성 assets 연결 | Android CI/SDK 빌드, 선택 R2 |
| P7.5 | 완료(PoC) | grounded template 기본, 사실 facet LLM 우회, Ollama 옵트인, SSE fallback | 선택 LLM FACTS 벤치 |
| P8 | 미착수 | 없음 | Internal/Closed Test와 릴리즈 QA |

추가 검증:
- 폼·진화 조건과 passage 확장 후에도 DB를 9.15MB로 유지했다.
- 저신뢰 스캔은 사용자 후보 확정 전 컬렉션 저장이 비활성화된다.
- 품질 로그는 원본 이미지/OCR 전문을 저장하지 않고 엔진, 점수, 버전, latency, 확정 여부만 최대 100건 보관한다.
- 웹 PoC는 PO/UIUX 품질 게이트 97/100으로 이해관계자 사용성 평가 진입 가능하다.
- 360×800 최초 진입에서 촬영 CTA가 화면 안에 노출되고 가로 넘침과 브라우저 경고·오류가 없다.
- 정식 MVP/Production은 P2, P3–P5, 정식 라이선스 승인 전까지 No-Go다.

## 5. 변경 이력

| 수정일자 | 수정자 | 변경 대상 문서 | 수정 요약 | 반영 상태 |
| :-- | :-- | :-- | :-- | :-- |
| 2026-07-29 09:53 +09:00 | Codex | `docs/specs/prod_단계별_작업계획.md` | 웹 PoC 97점·모바일 브라우저 검증 및 정식 MVP 잔여 게이트 반영 | 완료 |
| 2026-07-29 09:41 +09:00 | Codex | `docs/specs/prod_단계별_작업계획.md` | 실제 OCR·정확성·1,351폼·진화 조건·UI/UX·Android 소스·CI와 미검증 게이트 반영 | 완료 |
| 2026-07-28 18:04 +09:00 | Codex | `docs/specs/prod_단계별_작업계획.md` | P0/P1 완료 근거와 P2 이후 구현도, 상세·검색·컬렉션·품질 로그·DB 용량 최적화 상태 반영 | 완료 |
| 2026-07-28 17:47 +09:00 | Cursor | `docs/specs/prod_단계별_작업계획.md` | P6.5 Cascaded 실시간 게이트·P6.6 Voice Lab(OpenS2S/Moshi/Omni2) 실험 단계 반영 | 완료 |
| 2026-07-28 15:20 +09:00 | Codex | `docs/specs/prod_단계별_작업계획.md` | 모바일 360px 게이트, 보이스 프리뷰 API, 비모방 독자 AI 보이스 정책 반영 | 완료 |
| 2026-07-28 15:05 +09:00 | Codex | `docs/specs/prod_단계별_작업계획.md` | 1B SSE 스트리밍 채팅과 `/v1/chat` fallback 게이트 반영 | 완료 |
| 2026-07-28 19:45 +09:00 | Codex | `docs/specs/prod_단계별_작업계획.md` | 로컬 Ollama runtime 표시와 합법 음성 STS/TTS prototype 단계 추가 | 완료 |
| 2026-07-28 19:55 +09:00 | Codex | `docs/specs/prod_단계별_작업계획.md` | 1B LLM 프로파일 고정 단계 추가 | 완료 |
| 2026-07-28 19:20 +09:00 | Codex | `docs/specs/prod_단계별_작업계획.md` | prod까지 단계별 작업 계획과 Rotom UI 선행 게이트 저장 | 완료 |
