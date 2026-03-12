# 포켓덱스 구현 계획서 (Phase 1-10)

## 0. 계획 목적
- 본 문서는 포켓덱스 프로젝트를 `uv` 기반 Python 개발환경으로 구축하고, MVP를 단계적으로 구현하기 위한 실행 계획이다.
- 계획은 진행상황에 따라 업데이트 가능하다.

## 공통 원칙
- 패키지/실행은 `uv`를 기본으로 사용한다.
- Python 파일은 단독 실행 가능 구조를 유지한다.
- 모든 변경은 `docs/logs`와 `docs/rules` 정책을 따른다.

## Phase 1. 프로젝트 부트스트랩
- 목표:
  - 저장소 초기화와 기본 개발 구조 준비.
- 작업:
  - `git init` 수행
  - 기본 디렉토리 구조 점검(`app/`, `docs/`, `scripts/`)
  - `.gitignore` 초안 작성
- 완료 기준:
  - git 저장소 초기화 완료
  - 기본 디렉토리 규칙 확정

## Phase 2. uv/pyproject 설정
- 목표:
  - uv 기반 실행 환경 확정.
- 작업:
  - `pyproject.toml` 생성 및 업데이트
  - 런타임/개발 의존성 정의
  - `uv sync` 기준의 로컬 환경 재현 가능화
- 완료 기준:
  - `pyproject.toml`로 설치/실행 재현 가능

## Phase 3. 설정 계층(config) 구현
- 목표:
  - 최상위 config에서 `.env` 참조 체계 확정.
- 작업:
  - `app/config/settings.py`
  - `app/config/providers.py`
  - 환경별 키/옵션 validation
- 완료 기준:
  - `.env` 기반으로 모든 provider 초기화 가능

## Phase 4. LLM 라우팅 계층(LiteLLM) 구현
- 목표:
  - Solar/Gemini 라우팅 및 fallback 정책 구현.
- 작업:
  - LiteLLM 공통 호출 래퍼
  - router: `solar-mini`
  - main: `solar-pro2`
  - fallback: `gemini-flash`
  - 임계값 3종(timeout/error/quality) 게이트 적용
- 완료 기준:
  - fallback 동작 및 trace 태깅 검증 완료

## Phase 5. 데이터 계층 구현(Supabase + Graph DB)
- 목표:
  - 하이브리드 조회 기반 준비.
- 작업:
  - Supabase(PostgreSQL/pgvector) 연결
  - Graph DB(무료 티어 우선) 연결
  - 공통 repository 인터페이스 정의
- 완료 기준:
  - DB 양쪽에서 최소 조회 API 동작

## Phase 6. GraphRAG 파이프라인 구현
- 목표:
  - 벡터 검색 + 그래프 탐색 컨텍스트 합성.
- 작업:
  - 검색 쿼리 표준화
  - context merger 노드 구현
  - degraded mode(한쪽 실패 시 축소 동작) 구현
- 완료 기준:
  - Hybrid GraphRAG 응답 컨텍스트 생성 성공

## Phase 7. 에이전트 골격 구현(graph/state/tool/node)
- 목표:
  - 핵심 실행 구조 완성.
- 작업:
  - `graph.py`, `state.py`
  - `tools/*`, `nodes/*` 최소 실행 버전
  - 노드별 I/O 스키마 검증
- 완료 기준:
  - 단일 요청 end-to-end 실행 가능

## Phase 8. 기능 API 구현(MVP)
- 목표:
  - MVP 핵심 API를 제공.
- 작업:
  - `chat`, `scan`, `pokedex` 라우트 구현
  - 인증 연계(로그인 사용자 기준 메모리 영구)
  - 날씨 반영 응답(톤 + 추천 로직)
- 완료 기준:
  - MVP API 수동 테스트 통과

## Phase 9. 관측성/품질 체계 구축
- 목표:
  - 운영 가능한 추적/품질 지표 확보.
- 작업:
  - Langfuse trace/span/token 기록
  - fallback, latency, error 모니터링
  - 품질 스코어 계산기(quality gate) 도입
- 완료 기준:
  - 요청별 trace_id 추적 가능

## Phase 10. 릴리즈 준비 및 운영 전환
- 목표:
  - 단일 리전 배포 가능한 상태 확보.
- 작업:
  - 운영 환경 변수 정리
  - 배포/롤백 절차 문서화
  - 최종 점검 체크리스트 수행
- 완료 기준:
  - 단일 리전 MVP 배포 준비 완료

## 즉시 실행 백로그(Next Actions)
1. Phase 1 착수: `git init`, `.gitignore` 생성
2. Phase 2 착수: `pyproject.toml` 생성 및 uv 의존성 확정
3. Phase 3 착수: `settings.py/providers.py` 스캐폴딩
