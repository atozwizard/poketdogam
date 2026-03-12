# 설계서: 핵심 주의점 반영 가중치 설계 및 출력 리포트 포맷

## 1. 목적
- 파싱 텍스트 기반 요구역량 추론에서 발생하는 편향/노이즈를 줄이기 위한 가중치 체계를 정의한다.
- 결과를 검증 가능하게 전달하기 위한 표준 출력 리포트 포맷(JSON/Markdown)을 정의한다.

## 2. 핵심 주의점과 보정 전략
- 브랜드/네비게이션 단어 과대표집: 감점 가중치 적용
- 깨진 토큰/인코딩 노이즈: 품질 패널티 적용
- 반복 문구/중복 청크: 중복 감쇠 가중치 적용
- 빈도 기반 허위 연관: 관계 타입별 신뢰도 계수 적용
- 한영 혼합 매핑 누락: 동의어 매핑 성공률 보정 적용

## 3. 가중치 설계

### 3.1 입력 변수
- `tf_norm(k)`: 키워드 정규화 빈도(0~1)
- `edge_conf(e)`: 관계 엣지 신뢰도(0~1)
- `chunk_quality(ch)`: 청크 품질 점수(0~1)
- `dup_ratio(ch)`: 중복 비율(0~1)
- `noise_ratio(doc)`: 노이즈 토큰 비율(0~1)
- `nav_ratio(doc)`: 네비게이션/푸터 토큰 비율(0~1)

### 3.2 키워드 기여 점수
- `kw_score(k,c) = tf_norm(k) * map_weight(k,c) * qual_adj(k)`
- `map_weight(k,c)` 기본값: 1.0
- `qual_adj(k)`:
- 일반 키워드 1.0
- 브랜드/메뉴성 키워드 0.35
- 깨진 토큰/의심 토큰 0.1
- 스펙 숫자(`70b`, `31b`) 0.6 (단, C2에서만 유효)

### 3.3 관계 기여 점수
- `edge_score(e,c) = edge_conf(e) * rel_weight(relation_type) * evidence_adj(e)`
- `rel_weight` 기본값:
- `REQUIRES`: 1.3
- `IMPROVES`: 1.2
- `EVALUATED_BY`: 1.1
- `USED_IN`: 1.0
- `RELATED_TO`: 0.7
- `TRADE_OFF`: 0.8
- `evidence_adj(e)`:
- 동일 문장 근거: 1.1
- 인접 문장 근거: 1.0
- 동일 청크 내 약한 공출현: 0.85

### 3.4 역량 원점수
- `raw_competency_score(c) = Σ kw_score(k,c) + Σ edge_score(e,c)`

### 3.5 문서 보정 계수
- `doc_adj = (1 - 0.4*noise_ratio) * (1 - 0.35*nav_ratio) * (1 - 0.3*dup_ratio_mean)`
- 하한값: `min(doc_adj, 0.55)`가 아니라 `max(doc_adj, 0.55)`를 적용해 과도한 감쇠 방지

### 3.6 최종 점수
- `final_score(c) = normalize_0_100(raw_competency_score(c)) * doc_adj`
- `confidence(c) = clamp(0,1, 0.5*evidence_coverage + 0.3*edge_conf_mean + 0.2*chunk_quality_mean)`

## 4. 확률 산출
- `P(c) = softmax(final_score(c)/tau)`
- 권장 온도 `tau = 12`
- 리포트에는 `probability`, `final_score`, `confidence`를 함께 제공

## 5. 다양성 지표
- `competency_coverage = active_competencies / total_competencies`
- `entropy_competency = -Σ P(c)log(P(c))`
- `source_balance = 1 - gini(source_contribution)`

판정 예시
- 다양성 높음: coverage >= 0.6 and entropy 상위 구간
- 집중형: 상위 2개 역량 확률 합 >= 0.7

## 6. 출력 리포트 포맷

### 6.1 JSON 스키마 (요약)
```json
{
  "job_role": "AI Agent Product Engineer",
  "run_id": "2026-03-10T14:00:00+09:00",
  "document_scope": {
    "doc_count": 12,
    "chunk_count": 240,
    "language_mix": "ko-en"
  },
  "quality": {
    "noise_ratio": 0.08,
    "nav_ratio": 0.21,
    "dup_ratio_mean": 0.15,
    "doc_adjustment": 0.79
  },
  "competencies": [
    {
      "code": "C5",
      "name": "서비스 성능 최적화",
      "final_score": 86.4,
      "probability": 0.24,
      "confidence": 0.81,
      "top_keywords": ["latency", "throughput", "performance"],
      "top_relations": [
        {"type": "EVALUATED_BY", "weight": 1.1, "confidence": 0.84}
      ],
      "evidence_chunks": ["doc3#ch12", "doc5#ch4"]
    }
  ],
  "diversity": {
    "competency_coverage": 0.7,
    "entropy_competency": 1.91,
    "source_balance": 0.74
  },
  "risks": [
    "navigation_tokens_high",
    "encoding_noise_detected"
  ]
}
```

### 6.2 Markdown 리포트 템플릿
```md
# 요구역량 추론 리포트
- 직무: AI Agent Product Engineer
- 실행시각: 2026-03-10 14:00 (KST)
- 문서/청크: 12 / 240

## 품질 요약
- 노이즈 비율: 8%
- 네비게이션 비율: 21%
- 중복 평균: 15%
- 문서 보정계수: 0.79

## 상위 요구역량
| 순위 | 코드 | 역량명 | 점수 | 확률 | 신뢰도 |
|---|---|---|---:|---:|---:|
| 1 | C5 | 서비스 성능 최적화 | 86.4 | 0.24 | 0.81 |
| 2 | C4 | 툴·API 통합 | 82.1 | 0.21 | 0.78 |
| 3 | C6 | 신뢰성·운영 안정화 | 79.8 | 0.19 | 0.76 |

## 근거
- C5: latency, throughput, performance (doc3#ch12, doc5#ch4)
- C4: api, integration, tool, interface (doc2#ch7)
- C6: production, deployment, stable, reliability (doc4#ch9)

## 리스크
- navigation_tokens_high
- encoding_noise_detected
```

## 7. 운영 규칙
- 상위 역량은 `점수`가 아니라 `점수+확률+신뢰도` 3축으로 해석한다.
- `confidence < 0.6` 역량은 자동 의사결정에 사용하지 않고 검토 대상으로 분류한다.
- 리포트 저장 시 원문 근거 청크 ID를 반드시 포함한다.
