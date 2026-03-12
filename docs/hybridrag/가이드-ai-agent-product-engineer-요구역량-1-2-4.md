# 가이드-ai-agent-product-engineer-요구역량-1-2-4

## 범위
- 대상 직무: `AI Agent Product Engineer`
- 목적: 키워드/관계 그래프에서 요구 역량을 추출하기 위한 최소 공통 기준 정의
- 본 문서는 이전 정의의 `1(역량 온톨로지)`, `2(관계 의미 타입)`, `4(키워드→역량 매핑 규칙)`만 포함한다.

## 1. 역량 온톨로지 (Competency Ontology)

| 역량 코드 | 역량명 | 정의 | 관찰 가능한 신호(예시 키워드) |
|---|---|---|---|
| C1 | 에이전트 아키텍처 설계 | 단일/멀티 에이전트 구조, 상태, 도구 경계를 설계하는 능력 | agent, multi-agent, orchestrator, graph, state, workflow |
| C2 | 모델 선택·평가 | 목적/비용/품질 기준으로 모델을 고르고 성능을 검증하는 능력 | model, benchmark, quality, accuracy, reasoning, eval |
| C3 | 프롬프트·정책 엔지니어링 | 시스템 지시/가드레일/출력 포맷을 안정적으로 설계하는 능력 | instruction, system, response, consistency, format, policy |
| C4 | 툴·API 통합 | 외부 API/도구/함수 호출을 제품 플로우로 연결하는 능력 | api, tool, calling, integration, service, interface |
| C5 | 서비스 성능 최적화 | 지연/처리량/비용을 조정하여 운영 품질을 맞추는 능력 | latency, throughput, performance, efficiency, scale |
| C6 | 신뢰성·운영 안정화 | 장애/변동 조건에서 안정적으로 동작하게 만드는 능력 | reliability, stable, consistent, production, deployment |
| C7 | 데이터·지식 연결(RAG) | 문서/지식 검색 및 컨텍스트 주입 파이프라인 구성 능력 | retrieval, context, document, knowledge, chunk, vector |
| C8 | 제품화·실험 운영 | 사용자 가치 검증, 릴리스, 개선 루프를 운영하는 능력 | user, experience, release, preview, improvements, metrics |
| C9 | 도메인·언어 적응 | 한국어/영어 및 도메인 특성에 맞게 품질을 맞추는 능력 | korean, english, multilingual, domain, preference |
| C10 | 책임·거버넌스 | 안전, 규정, 프라이버시 요구를 제품 수준으로 반영하는 능력 | privacy, policy, safety, compliance, terms |

온톨로지 운영 규칙
- 한 키워드는 복수 역량에 매핑될 수 있다. 단, 1순위 역량(Primary) 1개는 반드시 지정한다.
- 역량 점수 산출 단위는 문서 단위와 코퍼스 단위를 분리한다.
- 숫자 토큰(예: `2025`, `70b`)은 기본적으로 역량 신호가 아니라 메타 신호로 분리한다.

## 2. 관계 의미 타입 (Typed Relations)

| 관계 타입 | 의미 | 방향 | 예시 |
|---|---|---|---|
| REQUIRES | 역량 A 수행에 역량/기술 B가 선행 필요 | A -> B | `에이전트 아키텍처` -> `툴·API 통합` |
| ENABLES | A가 있으면 B를 가능하게 함 | A -> B | `데이터·지식 연결` -> `도메인 적응` |
| IMPROVES | A가 B의 품질/성능을 높임 | A -> B | `프롬프트 엔지니어링` -> `모델 품질` |
| TRADE_OFF | A를 높이면 B가 감소/비용 증가 가능 | A <-> B | `throughput` <-> `accuracy` |
| EVALUATED_BY | A를 B 지표로 평가함 | A -> B | `서비스 성능` -> `latency/throughput` |
| IMPLEMENTED_BY | 역량이 특정 구현 방식으로 실체화됨 | A -> B | `신뢰성` -> `retry/fallback` |
| USED_IN | 기술/요소가 특정 역량 문맥에서 사용됨 | 기술 -> 역량 | `api` -> `툴·API 통합` |
| RELATED_TO | 의미 연관은 있으나 인과/평가 방향 미확정 | A <-> B | `reasoning` <-> `quality` |

관계 생성 최소 기준
- 단순 빈도 기반 연결은 `RELATED_TO`만 허용한다.
- `REQUIRES/IMPROVES/TRADE_OFF`는 원문 문장 근거(동일 문장 또는 인접 문장 2개 이내)가 있을 때만 생성한다.
- 엣지에는 `weight`, `confidence`, `evidence_chunk_id`를 필수 저장한다.

권장 속성 스키마 (edge)
- `source`, `target`, `relation_type`, `weight`, `confidence`, `doc_id`, `chunk_id`, `timestamp`

## 4. 키워드 -> 역량 매핑 규칙 (Mapping Rules)

### 4.1 기본 규칙
- 정규화: 소문자화, 복수형/변형 통합(`model/models`, `llm/llms`), 오탈자 사전 보정.
- 불용어 제거 후 남은 키워드만 사용.
- 숫자 토큰은 기본 제외, 모델 스펙(`70b`, `31b`)은 `C2 모델 선택·평가`의 보조 신호로만 사용.

### 4.2 점수 규칙
- 키워드 1개가 역량 사전과 매칭되면 기본점수 `+1`.
- 키워드 빈도가 상위 10%이면 가중치 `x1.5`.
- 같은 청크에서 동일 역량 키워드가 3개 이상 동시출현하면 보너스 `+2`.
- `IMPROVES/REQUIRES` 타입 엣지로 연결된 키워드쌍이 확인되면 해당 역량 점수 `+1` 추가.

### 4.3 역량 판정 임계값(문서 단위)
- `0~2`: 신호 약함
- `3~5`: 신호 중간
- `6+`: 핵심 요구 역량

### 4.4 직무 특화 우선순위 (`AI Agent Product Engineer`)
- 1순위 핵심군: `C1, C4, C5, C6, C8`
- 2순위 핵심군: `C2, C3, C7`
- 보정군: `C9, C10`

우선순위 적용 규칙
- 동점일 때 1순위 핵심군을 우선 채택한다.
- 제품 문맥 키워드(`user`, `experience`, `release`, `metrics`)가 충분하면 `C8` 점수에 `+1` 보정.
- 운영 문맥 키워드(`production`, `deployment`, `stable`, `reliability`)가 충분하면 `C6` 점수에 `+1` 보정.

### 4.5 예시 매핑 (현재 대화 맥락 키워드 기준)
- `api, tool, calling, interface` -> `C4 툴·API 통합`
- `latency, throughput, performance, efficiency, scale` -> `C5 서비스 성능 최적화`
- `production, deployment, stable, reliability, consistent` -> `C6 신뢰성·운영 안정화`
- `reasoning, quality, accuracy, benchmark` -> `C2 모델 선택·평가`
- `user, experience, improvements, release, preview` -> `C8 제품화·실험 운영`

## 적용 메모
- 이 문서는 그래프/VectorDB 하이브리드 파이프라인의 역량 추론 기준으로 사용한다.
- 추론 결과 보고 시 각 역량별 상위 근거 키워드와 근거 청크 ID를 함께 제시한다.
