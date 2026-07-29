# OpenS2S 감정 Speech-to-Speech · 사용자별 멀티턴 메모리 서베이

## 0. 문서 목적
- OpenS2S로 **감정을 고려한 Speech-to-Speech(S2S)** 를 Poketdogam에 넣는 가능 경로를 조사한다.
- **사용자별 멀티턴**을 지원하고, **기억할 대화 최대 3000건**을 만족하는 저장·검색 방식을 비교한다.
- 기준 제약: 유료 API 금지, 상시 인스턴스 비선호, 모바일 온디바이스 핫패스 유지.

## 1. 현황 (As-Is)
| 영역 | 현재 |
| --- | --- |
| Voice | `browser_speech_synthesis` 프리뷰만 (`/v1/voice/*`). 감정 S2S 없음 |
| Session | `sessions.sqlite` + `flow_state`, TTL 1800s, **MAX_TURNS=24** |
| 사용자 식별 | `user_id` 필드만 있고 실제 키잉/격리 미흡 |
| RAG | 로컬 Dex passages + hash embed (도감 지식). 대화 장기기억과 분리됨 |

---

## 2. OpenS2S 서베이

### 2.1 무엇인가
- 논문/코드: [OpenS2S (CASIA-LM)](https://github.com/CASIA-LM/OpenS2S), arXiv:2507.05177  
- **완전 오픈소스** end-to-end **공감형(empathetic) Large Speech Language Model**
- 목표: 음성의 운율·감정 단서(paralinguistics)를 이해하고, **감정 표현이 있는 음성 응답**을 생성
- Apache-2.0, 가중치·데이터·학습 코드 공개 지향

### 2.2 구조 (감정 S2S가 되는 이유)
```text
User Speech
  → Audio Encoder (운율/감정 포함 임베딩)
  → Instruction LLM (Qwen3-8B-Instruct)  ← 텍스트+오디오 interleaved
  → Streaming Speech Decoder (semantic speech tokens → waveform)
  → Empathetic Spoken Reply
```
- 선행: BLSP-Emo (empathetic speech-to-text)
- 디코더: supervised semantic tokenizer + AR TTS LM (예: GLM-4-Voice decoder 계열 자산과 연동 문서화)
- **감정은 별도 분류기만의 문제가 아니라**, 인코더→LLM→디코더 전 구간에 실린다.

### 2.3 배포 현실성 (Poketdogam 관점)
| 항목 | 평가 |
| --- | --- |
| 모바일 온디바이스 | **비현실적** (LLM ~8B + 음성 인코더/디코더). 1B 텍스트와 비교 불가 |
| 로컬 GPU 서버 | 가능. Qwen3-8B급은 FP16 ~16–20GB, 양자화 시 여유 있으나 **오디오 스택 추가 VRAM** 필요 |
| Cloudflare Workers AI 무료 | **불가** (모델 미제공·용량·스트리밍 S2S 비적합) |
| 라이선스 | Apache-2.0으로 연구/비상업 실험에 유리. 상용·IP(로토무 성우 혼동)는 별도 정책 유지 |
| 현재 voice 정책과의 정합 | 공식 성우 모방 금지. OpenS2S는 **독자 합성 보이스**로만 사용 |

### 2.4 도입 방안 비교

#### 방안 A — OpenS2S End-to-End (이상적 품질)
```text
App mic → upload/stream audio
  → OpenS2S GPU service (optional)
  → spoken audio + optional transcript/emotion tags
  → (parallel) local Dex RAG for facts
```
- **장점:** 감정 인식·생성 일체, 스트리밍 디코딩으로 지연 완화  
- **단점:** GPU 상시/온디맨드 필요, 앱 번들 불가, 비용·운영 부담  
- **적합:** Phase “Voice Lab / 데스크톱·홈서버 옵션”

#### 방안 B — Cascaded Emotion STS (권장 MVP 경로)
OpenS2S 전체 대신 **감정 파이프라인을 분해**해 단계 도입:
1. **Emotion-aware ASR / SER**  
   - 음성 → 텍스트 + `emotion`/`arousal`/`valence` 태그  
   - 후보: 경량 SER 모델, Whisper 계열 + 별도 emotion head, 또는 OpenS2S의 STT 경로만 차용
2. **로컬 텍스트 에이전트 (기존)**  
   - Rotom prompt + Dex RAG + session memory  
   - system에 `USER_EMOTION=excited|curious|frustrated…` 주입 → 말투/공감 조절
3. **Emotion-conditioned TTS**  
   - 스타일 토큰/지시문 TTS (예: Qwen3-TTS CustomVoice instruction, 오픈 TTS + style)  
   - 앱 정책상 **전기 디바이스 독자 보이스**만 허용

```text
mic → [SER+ASR] → {text, emotion}
  → Rotom Agent + Memory + Dex RAG → reply_text + reply_emotion
  → Emotion TTS → speaker
```
- **장점:** 온디바이스/소형 서버에 단계 배치 가능, 기존 챗 스택 재사용  
- **단점:** E2E만큼 운율 정렬이 매끄럽지 않을 수 있음  

#### 방안 C — 하이브리드 게이트
- 기본: B (로컬/경량)  
- 사용자 옵트인 + Wi‑Fi + (옵션) 홈 GPU: A (OpenS2S)  
- 쿼터/실패 시 B로 degrade  

### 2.5 OpenS2S를 쓸 때 권장 아키텍처 (옵션 서비스)
```text
[Mobile App]
  capture PCM/Opus → POST /v1/voice/s2s (session_id, user_id)
  play streamed audio

[Voice Gateway — optional, not MVP hot path]
  auth + rate limit
  OpenS2S worker (GPU)
  sidechannel: transcript, emotion_label → Agent for Dex grounding

[Always-local]
  Dex SQLite + Session Memory (아래 3절)
  template/1B text fallback if voice service down
```

### 2.6 감정 태그 스키마 (제안)
```json
{
  "user_emotion": {"label": "curious", "valence": 0.4, "arousal": 0.6, "confidence": 0.72},
  "reply_emotion": {"label": "encouraging", "style": "electric_device"},
  "policy": {"official_mimicry": false}
}
```
- UI 표정(`think/happy/surprise…`)과 `reply_emotion` 매핑
- Rotom system prompt에 “공감하되 FACTS 밖 창작 금지” 유지

### 2.7 단계별 로드맵 (권장)
| Phase | 내용 |
| --- | --- |
| V0 (현재) | Browser TTS preview |
| V1 | Cascaded: streaming STT + emotion heuristic/SER lite + style TTS + barge-in (TTFA≤1.5s) |
| V2a | 서버 옵션 OpenS2S S2S (옵트인), Dex grounding sidechannel |
| V2b | Moshi 풀듀플렉스 옵트인 (체감 데모) |
| V2c | LLaMA-Omni2-0.5B-Bilingual 튜닝 실험 (학술/격리) |
| V3 | Android native audio pipeline + 동일 API |

**결론 (OpenS2S):**  
감정 S2S의 **품질 상한선 후보**로 적합하나, **모바일 온디바이스 메인은 아니다**.  
Poketdogam은 **B(캐스케이드)를 기본**, OpenS2S는 **옵션 GPU 경로**로 설계하는 것이 제약과 맞다.

### 2.8 Moshi / 소형 STS / Cascaded 실시간 / Omni2 (교차 문서)
스레드에서 추가로 확정·기록한 항목은 아래 문서에 **전량** 있다. 본 절은 인덱스만 둔다.

→ **`docs/specs/음성_STS_실시간대화_및_Omni2실험_계획.md`**

포함 내용:
1. Moshi(Kyutai) ~200ms 풀듀플렉스 평가 — GPU 옵션, 폰 핫패스 불가, EN 주력, Dex sidechannel 필요
2. STS 가능 소형 모델 표 — LLaMA-Omni2 0.5B, Mini-Omni, UniSS 0.5B(번역), Hibiki/Seamless/SimulTron(통역), 경량 Cascaded가 실무 최소 STS
3. Cascaded로 실시간 대화 가능 여부 — 턴제+스트리밍+barge-in = Yes / Moshi급 full-duplex = No(naive)
4. LLaMA-Omni2 0.5B 튜닝 실험 E0–E4, Go/No-Go, NC 라이선스
5. V1 게이트 TTFA≤1.5s

---

## 3. 사용자별 멀티턴 · 기억 3000건 서베이

### 3.1 “3000건” 해석
| 해석 | 의미 | 권장 처리 |
| --- | --- | --- |
| A. 사용자당 **대화 세션 3000개** | 과거 채팅방/스레드 | `conversations` 테이블 soft-cap |
| B. 사용자당 **기억 유닛 3000개** | 요약·에피소드·사실 메모리 | **권장 해석** (실무적으로 유용) |
| C. 사용자당 **원문 턴 3000개** | 메시지 3000줄 | 가능하나 컨텍스트 주입엔 비효율 |

본 문서 권장: **B를 hard cap**, A/C는 원문 보관 한도로 병행.

### 3.2 요구사항 정리
1. **사용자별 격리** (`user_id` 파티션)
2. **멀티턴 연속성** (대명사/이전 포켓몬/감정)
3. **기억 상한 3000** (초과 시 eviction)
4. 온디바이스/로컬 우선 → **SQLite (+ 선택 벡터)**  
5. 프롬프트에는 전부 넣지 말고 **검색으로 소량만 주입**

### 3.3 메모리 계층 (업계 공통 패턴)
Oracle/에이전트 메모리 서베이와 ThinkFlow 세션 모델에 맞춘 4층:

| Layer | 내용 | 보관 | 프롬프트 주입 |
| --- | --- | --- | --- |
| L0 Working | 현재 발화·감정 | RAM | 항상 |
| L1 Recent | 최근 N턴 (예: 12–24) | SQLite turns | 항상 |
| L2 Episodic | 세션 요약·중요 사건 | SQLite + embed | 검색 Top-k |
| L3 Semantic/Profile | 선호·자주 찾는 포켓몬·톤 | SQLite structured | 슬롯 + 검색 |

현재 코드는 L1 일부만 존재 (`MAX_TURNS=24`). L2/L3와 `user_id` 격리가 필요.

### 3.4 저장소 옵션 비교

| 방식 | 3000건/유저 | 멀티유저 | 오프라인 | 복잡도 | Poketdogam 적합 |
| --- | --- | --- | --- | --- | --- |
| **SQLite per device + user_id** | 충분 (수천~수만 행) | 기기 로컬 계정 | 최상 | 낮음 | **1순위** |
| SQLite + FTS5 + hash/local embed | 의미 검색 가능 | 동일 | 최상 | 중 | **1순위+** |
| sqlite-vec / 로컬 FAISS 파일 | 벡터 검색 강화 | 동일 | 상 | 중 | 2순위 |
| Cloudflare D1/R2 sync | 기기 간 동기화 | 무료 한도 주의 | 부분 | 중 | 콜드패스 |
| Supabase (sync only) | 서버 백업 | Free 한도 | 아니오 | 중 | 후순위 |
| 전문 Vector DB (Milvus 등) | overkill | 서버 필요 | 아니오 | 높음 | 비권장 |

**용량 감:**  
기억 유닛 평균 400B 텍스트 + 256-d float32 embed(~1KB) ≈ **~1.4KB/건**  
3000건 ≈ **~4MB/유저** → 모바일·SQLite에 무리 없음.

### 3.5 Eviction 전략 (3000 캡)
초과 시 단순 FIFO보다 **점수 eviction** 권장:
```text
score = 0.45*importance + 0.30*recency + 0.15*access_count - 0.10*duplication
keep top 3000 by score; archive or delete rest
```
- `importance`: 사용자가 “기억해”, 컬렉션 저장, 감정 peak, 진화/약점 등 facet
- `recency`: exponential decay (예: half-life 14–30일)
- 원문 turns는 세션당 최근 24개만 핫 유지, 나머지는 요약으로 압축

### 3.6 검색·주입 전략 (ThinkFlow + 기존 RAG와 정렬)
```text
new_user_utterance
  → ensure user_id + session_id
  → L1 recent turns
  → retrieve L2/L3 memories (hybrid FTS + hash/vector, user_id filter)
  → merge with Dex RAG (facts)  # 기억과 도감 분리 채널
  → assemble prompt under token budget
  → answer + write new turn
  → async: summarize / extract memories / enforce 3000 cap
```
- **Dual retrieve:** (A) 대화 기억 채널 (B) Dex 팩트 채널 — ThinkFlow dual retrieve와 동일 사상
- Follow-up carryover는 기존 `flow_state` 유지 + L2 recall 보강

### 3.7 스키마 초안 (제안)
```sql
users(user_id pk, created_at, prefs_json)

conversations(
  conversation_id pk, user_id, title, created_at, last_active_at, turn_count
)

turns(
  turn_id pk, conversation_id, user_id, role, content,
  emotion_json, metadata_json, created_at
)

memories(
  memory_id pk, user_id,
  kind,              -- episode|fact|preference|emotion
  content,           -- 요약 텍스트
  importance real,
  access_count int,
  embedding_csv text,-- 또는 blob
  source_turn_ids text,
  created_at, last_access_at
)

-- indexes: (user_id, last_access_at), FTS on memories.content
-- constraint logic: count(memories where user_id=?) <= 3000
```

### 3.8 “가능한 방법” 요약 매트릭스

| 방법 | 설명 | 3000건 | 추천 |
| --- | --- | --- | --- |
| Sliding window only | 최근 N턴만 | 장기기억 불가 | 부족 |
| Full transcript dump | 과거 전부 프롬프트 | 토큰 폭발 | 비권장 |
| Rolling summary | 세션마다 요약 갱신 | 가능 | 필수 층 |
| Episodic memory store | 사건 단위 3000 | 최적 | **채택** |
| Profile slots | 선호 포켓몬/톤 | 소량 | **채택** |
| Vector recall | 유사 과거 대화 검색 | 스케일 OK | **채택(해시→로컬)** |
| Graph memory | 엔티티 관계 | 복잡도↑ | 후순위 |

### 3.9 권장 구현 순서
1. `user_id` 필수화 + conversation/turn 스키마  
2. L1 recent 24턴 유지 (현재 확장)  
3. `memories` 테이블 + **user 3000 + score eviction**  
4. 턴 종료 후 경량 추출(규칙/소형 LLM): 선호·자주 묻는 facet·감정 peak  
5. hybrid recall을 chat assemble에 연결  
6. (옵션) 기기 간 sync는 R2/D1 또는 Supabase **콜드패스만**

---

## 4. 통합 권고 (Poketdogam)

```text
[Hot path — device]
  Scan/Dex RAG (기존)
  Text chat + session L1 + memories≤3000
  Cascaded emotion STS (V1)  # TTFA≤1.5s, barge-in

[Optional — GPU Voice Lab]
  OpenS2S empathetic S2S
  Moshi full-duplex demo
  LLaMA-Omni2-0.5B tuning experiment (NC/학술 격리)
  → transcript/emotion sidechannel into same Agent+Memory
  → fail → Cascaded
```

| 우선순위 | 결정 |
| --- | --- |
| P0 | 사용자별 멀티턴 + memories 3000 cap (SQLite) |
| P1 | Cascaded emotion STS (감정 태그 → Rotom 톤 → style TTS + barge-in) |
| P2 | OpenS2S 옵트인 서버 |
| P2b | Moshi 옵트인 (풀듀플렉스) |
| P2c | LLaMA-Omni2-0.5B 실험 (상세: 음성_STS 계획 문서) |
| P3 | 크로스 디바이스 memory sync |

## 5. 리스크·열린 질문
1. OpenS2S/Moshi/Omni2 GPU를 **누가 호스팅**할지 (완전 로컬 홈서버 vs 공유 무료 불가)  
2. 3000건이 **세션**인지 **메모리 유닛**인지 제품 정의 확정 필요 → 본 문서는 메모리 유닛 권장  
3. 감정 S2S와 로토무 IP: 공식 음색 혼동 방지 UX 고지  
4. 한국어 감정 SER/TTS 품질 벤치 필요  
5. Omni2 비상업 라이선스와 제품 배포 충돌  
6. Cascaded TTFA 1.5s 저사양 달성 여부  

## 6. 참고 링크
- OpenS2S GitHub: https://github.com/CASIA-LM/OpenS2S  
- OpenS2S paper: https://arxiv.org/abs/2507.05177  
- Project page: https://casia-lm.github.io/OpenS2S  
- Moshi / Omni2 / Cascaded 실시간 상세: `docs/specs/음성_STS_실시간대화_및_Omni2실험_계획.md`  
- Agent memory patterns: layered STM/LTM + hybrid retrieval (Oracle developers blog; open-source agent-memory / SQLite+HNSW examples)  
- 내부 정렬: ThinkFlow FS-SESSION / FS-RAG, 본 프로젝트 `session/` + `rag/`

## 7. 변경 이력

| 수정일자 | 수정자 | 변경 대상 문서 | 수정 요약 | 반영 상태 |
| :-- | :-- | :-- | :-- | :-- |
| 2026-07-28 17:47 +09:00 | Cursor | `docs/specs/OpenS2S_감정STS_및_멀티턴메모리_서베이.md` | Moshi/소형STS/Cascaded실시간/Omni2 교차절·로드맵·우선순위 확장 | 완료 |
| 2026-07-28 16:45 +09:00 | Cursor | `docs/specs/OpenS2S_감정STS_및_멀티턴메모리_서베이.md` | OpenS2S 감정 S2S 도입 경로와 사용자별 3000건 메모리 서베이 초안 | 완료 |
