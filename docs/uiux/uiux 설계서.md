# UI/UX 설계서: Rotom Dex OS

## 0. 최신 결정
- UI 모티프는 **로토무**다. 단, 공식 아트나 캐릭터 원본을 복제하지 않고 전기, 디바이스, 표정, 장난스러운 말투를 추상화한 **Rotom Dex OS**로 구현한다.
- 기존 Solar/Upstage 기반 감정 엔진 전제는 폐기한다.
- MVP UI는 로컬 Dex, OS OCR, fuzzy matcher, 템플릿 응답 상태를 시각화한다.
- 실기기 연결 전에는 FastAPI 내장 웹 UI로 전체 UX를 완성하고, 이후 Android Kotlin + Jetpack Compose로 포팅한다.

## 1. 디자인 원칙
- 첫 화면은 앱 자체여야 한다. 마케팅 랜딩 페이지를 만들지 않는다.
- 화면은 “스마트폰 안에 전기 생명체가 도감 OS로 들어와 있다”는 느낌을 준다.
- 로토무 모티프는 다음 요소로 제한한다.
  - 밝은 주황/코랄 중심 바디
  - 청록색 전기 꼬리와 스캔 라인
  - 둥근 디바이스 바디와 귀/스파크 형태
  - 어두운 검정 배경이 아닌 밝은 크림/오렌지 계열 OS 화면
  - 얼굴형 상태 표시
  - 짧고 발랄한 상태 문장
  - 디바이스 프레임과 렌즈 UI
- 공식 포켓몬/로토무 이미지는 앱에 포함하지 않는다.
- 공식 로토무의 색감과 형태 언어는 참고하되, UI 자산은 프로젝트 고유의 추상 그래픽으로 만든다.

## 2. 실기기 전 UI 범위
- 웹 UI 제공 경로: `/`
- API:
  - `POST /v1/scan/text`: OCR fixture 텍스트를 스캔 입력처럼 처리
  - `POST /v1/chat`: 로컬 Dex 기반 템플릿 대화
  - `GET /v1/pokedex/forms/{form_id}`: 도감 상세
- 화면:
  1. 로토무 상태 헤더
  2. 스캔 렌즈
  3. OCR fixture 입력
  4. Top-3 후보
  5. 도감 상세
  6. 로토 대화
  7. 로컬 컬렉션
- 완료 기준:
  - `피카추 HP 60` 입력 시 피카츄 후보가 나온다.
  - 후보 선택 시 상세가 표시된다.
  - 같은 화면에서 대화 응답이 표시된다.
  - 모바일 폭에서도 텍스트와 버튼이 겹치지 않는다.

## 3. 상태 모델
- `idle`: 렌즈 대기.
- `scanning`: OCR fixture를 matcher에 보내는 중.
- `locked`: 0.90 이상 후보를 잠금.
- `low_confidence`: 후보는 있으나 사용자 확인 필요.
- `error`: Dex 없음, 후보 없음, API 실패.

## 4. 핵심 화면

### 4.1 로토무 상태 헤더
- 화면 상단에 추상화된 얼굴 표시를 둔다.
- 눈과 입은 상태에 따라 CSS class로 변한다.
- 표시 데이터:
  - dataset version
  - scan mode
  - 현재 상태

### 4.2 스캔 렌즈
- 카메라 실기기 연결 전에는 mock lens로 제공한다.
- 카드명 영역을 연상시키는 중앙 조준 프레임을 둔다.
- OCR fixture 입력을 렌즈 아래에 둔다.
- 샘플 버튼은 한글 OCR 오타와 띄어쓰기 케이스를 빠르게 넣는다.

### 4.3 후보 확인
- Top-3 후보를 confidence 순으로 표시한다.
- 각 후보는 이름, 타입, alias, score를 표시한다.
- score가 낮으면 확인 필요 상태를 유지한다.

### 4.4 도감 상세
- 이름, 영문명, 타입, 키/몸무게, 종족값 합계를 표시한다.
- 스탯은 전력 게이지 형태로 표현한다.
- source meta와 dataset version을 숨기지 않는다.

### 4.5 로토 대화
- 챗은 `/v1/chat/stream` SSE를 우선 사용해 같은 말풍선을 점진 갱신한다.
- 스트리밍 실패 시 기존 `/v1/chat` 완성형 응답으로 fallback한다.
- 로컬 Ollama 기본 개발 모델은 `llama3.2:1b`로 두고, 더 큰 모델은 프롬프트 실험용으로만 사용한다.
- 답변은 로토무 말풍선처럼 표시하되 공식 캐릭터 대사나 음성을 복제하지 않는다.
- UI에는 `template`, `ollama`, `fallback_template` 중 현재 LLM runtime을 표시한다.

### 4.6 음성 STS 모듈
- MVP에서는 실 STS 모델을 포함하지 않고 `pre_device_preview` 상태로 표시한다.
- 실기기 전 웹 UI에서는 browser speech synthesis 기반 프리뷰, pitch/speed/style 컨트롤, 정지 버튼을 제공한다.
- YouTube/공식 캐릭터 음성을 추출해 STS 음성으로 만들지 않는다.
- Prototype은 직접 녹음, 허가받은 음성, 공개 라이선스 음성, 또는 공식 음색을 모방하지 않는 독자 AI 합성 음성으로 만든 “전기 디바이스 보이스”만 사용한다.
- 공식 음성과 비슷하다고 홍보하거나 혼동될 정도의 유사성을 목표로 하지 않는다.

### 4.7 로컬 컬렉션
- 선택한 form을 브라우저 localStorage에 저장한다.
- Android 포팅 시 Room/SQLite 로컬 컬렉션으로 대체한다.

## 5. Android 포팅 기준
- Web UI의 화면 순서와 상태명을 그대로 Compose state로 옮긴다.
- CameraX 연결 전에는 fixture text 입력 화면을 남겨 개발 빌드에서 계속 사용할 수 있게 한다.
- ML Kit OCR 결과는 `/v1/scan/text`와 같은 shape의 내부 use case로 전달한다.
- UI copy, confidence threshold, 색상 token은 웹/Android가 같은 문서 기준을 따른다.
- 최소 모바일 폭 360px에서 nav, scan, detail, chat, voice controls에 가로 overflow가 없어야 한다.

## 6. 변경 이력

| 수정일자 | 수정자 | 변경 대상 문서 | 수정 요약 | 반영 상태 |
| :-- | :-- | :-- | :-- | :-- |
| 2026-07-28 15:20 +09:00 | Codex | `docs/uiux/uiux 설계서.md` | 모바일 최소 폭 기준과 보이스 프리뷰/비모방 AI 보이스 정책 반영 | 완료 |
| 2026-07-28 15:05 +09:00 | Codex | `docs/uiux/uiux 설계서.md` | 로토 대화 섹션에 1B SSE 스트리밍 우선 UX와 fallback 반영 | 완료 |
| 2026-07-28 19:45 +09:00 | Codex | `docs/uiux/uiux 설계서.md` | 검정 중심 UI를 밝은 Rotom 색감/형태 기준으로 조정하고 LLM runtime/STS 모듈 정책 반영 | 완료 |
| 2026-07-28 19:20 +09:00 | Codex | `docs/uiux/uiux 설계서.md` | Solar/Flutter 전제를 제거하고 Rotom Dex OS + 실기기 전 웹 UI 기준으로 최신화 | 완료 |
