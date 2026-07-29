# 음성 STS · 실시간 대화 · 소형 모델 · Omni2 실험 계획

> 수정 일자: 2026-07-28 17:47 +09:00  
> 관련: `OpenS2S_감정STS_및_멀티턴메모리_서베이.md`, `내부_전용_보이스_자산_운영안.md`, `prod_단계별_작업계획.md`, `온디바이스_무료티어_계획.md`, `구현_아키텍처_확정안.md`

## 0. 문서 목적
본 문서는 2026-07-28 스레드에서 논의한 **음성/STS/실시간 대화/소형 모델/튜닝 실험** 결정을 **요약이 아니라 항목별로 전부** 기록한다.  
제품 메인 경로와 연구 실험 경로를 분리해, 온디바이스·무료 티어 제약과 충돌하지 않게 한다.

---

## 1. 확정 제약 (음성 공통)
1. 유료 클라우드 LLM/STT/TTS API는 MVP 핫패스에서 사용하지 않는다.
2. 상시 서버 인스턴스는 MVP 핫패스에 두지 않는다. GPU 경로는 **옵트인 홈/연구 서버**만.
3. YouTube·공식 방송/게임 오디오 추출, 공식 로토무/성우 **음색 클로닝·모방** 금지.
4. 허용 보이스: 직접 제작·허가·공개 라이선스, 또는 **전기 디바이스 질감의 독자 AI 합성 음성**.
5. 도감 FACTS는 항상 로컬 Dex/Agent 쪽. 음성 모델이 팩트를 “기억”하게 만들지 않는다.
6. 한국어 UX가 기본. 영어 전용 SpeechLM은 데모/실험만.
7. 기존 Voice API 단계: `pre_device_preview` + `browser_speech_synthesis` (`/v1/voice/*`).

---

## 2. 모델·아키텍처 비교 (스레드 전체)

### 2.1 OpenS2S (CASIA-LM)
- 성격: 오픈소스 **공감형(empathetic) end-to-end S2S**. Qwen3-8B급 + 음성 인코더/디코더.
- 강점: 감정·운율 이해/생성 품질 상한선 후보.
- 약점: 모바일 온디바이스 비현실적. CF Workers AI 무료 경로 불가. GPU 필요.
- 결정: **옵션 GPU 경로 (Voice Lab)**. 제품 메인이 아님.
- Sidechannel: transcript + emotion → 기존 Rotom Agent + Dex RAG + memories.
- 상세: `OpenS2S_감정STS_및_멀티턴메모리_서베이.md` §2.

### 2.2 Moshi (Kyutai)
- 성격: 네이티브 멀티모달 **풀듀플렉스** Spoken Dialogue. Mimi codec + ~7B Temporal Transformer + Inner Monologue.
- 지연: 이론 ~160ms, L4 GPU 실측 ~200ms급.
- 강점: 끼어들기·동시 청취/발화·자연 대화 체감. 코드 Apache-2.0, 가중치 CC-BY 4.0.
- 약점:
  - PyTorch 추론 ~24GB VRAM급. MLX는 Apple Silicon 16GB+ 수준. **Android 핫패스 불가**.
  - 주력 언어 영어권. 한국어 UX 불확실.
  - 감정 라벨/스타일 API가 핵심이 아님 (OpenS2S와 역할 다름).
  - FAQ상 보이스/성격 변경은 파인튜닝 제한. 독자 로토무 보이스 정책과 맞추기 어려움.
  - Dex 도구호출·팩트 그라운딩 약함 → sidechannel 필수.
- 결정: **풀듀플렉스 체감용 GPU 옵션**. OpenS2S와 병행 가능하나 우선순위는 OpenS2S(감정) / Moshi(듀플렉스)로 구분.
- 비교 한 줄: Moshi=실시간 듀플렉스 최우선, OpenS2S=감정 표현 최우선, 둘 다 폰 메인 엔진 아님.

### 2.3 Cascaded Emotion STS (제품 MVP 권장)
```text
mic → [SER lite + streaming STT]
  → {text, emotion}
  → Rotom Agent + Dex RAG + session/memories
  → reply_text + reply_emotion
  → Emotion/style TTS (독자 electric_device 보이스)
  → speaker (+ barge-in)
```
- 장점: 온디바이스/경량 배치, 기존 챗·Dex 재사용, 모듈 교체 용이, IP 보이스 정책 준수 용이.
- 단점: E2E만큼 운율 정렬이 매끄럽지 않을 수 있음. naive 구현 시 지연↑.
- 결정: **제품 메인 음성 경로**.

### 2.4 Cascaded로 “실시간 대화”가 되는가?
| 레벨 | 정의 | MVP에서 |
| --- | --- | --- |
| A. Half-duplex 턴제 | 말 끝 → 답 | **목표 (필수)** |
| B. 스트리밍 STT/TTS | 첫 문장부터 재생, TTFA 단축 | **권장** |
| C. Barge-in | 재생 중 사용자 발화 → TTS 중단 | **권장** |
| D. Moshi급 full-duplex | 동시 청취·발화 | **비목표** (naive cascade 불가; DuplexCascade급 별도 설계 필요) |

**결론:** Cascaded로 **실시간 대화는 가능**하다. 다만 Moshi식 풀듀플렉스가 아니라 **턴제 + 스트리밍 + barge-in** 실시간이다.

실시간 체감 전제:
1. 스트리밍 STT·TTS (전체 답 대기 금지)
2. 짧은 답 (로토무 1~4문장, Dex 인용만)
3. 온디바이스 STT/TTS 우선 (RTT 제거)
4. barge-in (재생 중 mic)
5. Dex/에이전트는 텍스트 핫패스 유지

기대 지연(대략):
- 잘 짜인 온디바이스 cascade: 첫 소리(TTFA) ~0.8–2s
- 브라우저 STT + 서버 + 브라우저 TTS(현재 preview): 2–5s+ → 대화 체감 약함
- Moshi(~200ms)보다 느리지만 도감 Q&A에는 실용 범위

V1 수치 게이트(문서 고정):
- `TTFA ≤ 1.5s` (중급 Android, Wi‑Fi 불필요 로컬 경로)
- barge-in 성공 (재생 중 사용자 발화 시 TTS stop ≤300ms 목표)
- 한국어 STT/TTS 품질 주관 벤치 통과

### 2.5 “STS 가능한 작은 모델” 목록

#### 대화형 Spoken Dialogue (해당 제품 목적)
| 모델 | 규모 | 비고 | Poketdogam |
| --- | --- | --- | --- |
| **LLaMA-Omni2** | **0.5B~32B** | Qwen2.5 백본 + Whisper encoder + CosyVoice2 계열 디코더. 200K 멀티턴 S2S. EN 또는 EN+ZH Bilingual | **실험 후보 (0.5B-Bilingual)**. 제품 메인 X |
| Mini-Omni / Mini-Omni2 | ~소형 | 스트리밍 S2S·끼어들기. 출력 영어 중심. OSS TTS 제한 이슈 | 데모만 |
| UniSS 0.5B | 0.5B | 주 목적 **S2ST 번역** (EN–ZH) | 대화 에이전트 부적합 |
| Moshi / OpenS2S / Freeze-Omni / Qwen2.5-Omni | 7B+ | 품질·듀플렉스 우수 | “작지 않음”, 폰 핫패스 X |

**현실:** 폰에 올릴 만한 **한국어 대화형 native STS 소형 모델은 사실상 없음**.

#### 통역형 S2ST (참고만 — 도감 Q&A와 목적 다름)
- Hibiki-1B (Kyutai): 온디바이스 가능, FR→EN
- Seamless UnitY-Small (~281M): 온디바이스 S2ST, 언어 제한
- SimulTron: 연구용 온디바이스 동시통역

#### 실무상 “가장 작은 STS”
```text
경량 Cascaded ≈ 작은 STS 대체
  Whisper-tiny/base 또는 Android SpeechRecognizer
  + 템플릿 / 1B 텍스트 (Rotom+Dex)
  + Piper / Kokoro / 스타일 TTS (독자 보이스)
```

### 2.6 통합 권고 다이어그램
```text
[Hot path — device / MVP]
  Cascaded (STT + Rotom/Dex + style TTS)
  + barge-in + 짧은 답
  + memories≤3000 (별도 서베이 문서)

[Optional GPU — Voice Lab]
  A) OpenS2S — 감정/공감 S2S
  B) Moshi — 풀듀플렉스 체감
  C) LLaMA-Omni2-0.5B(-Bilingual) — 소형 S2S 튜닝 실험
  → 공통: transcript/emotion sidechannel → Agent+Dex+Memory
  → 실패 시 Cascaded로 degrade
```

| 우선순위 | 항목 |
| --- | --- |
| P0 | 사용자별 멀티턴 + memories 3000 (SQLite) — 서베이 문서 |
| P1 | Cascaded emotion STS V1 (TTFA≤1.5s, barge-in) |
| P2 | OpenS2S 옵트인 |
| P2b | Moshi 옵트인 (듀플렉스 데모) |
| P2c | **LLaMA-Omni2-0.5B 튜닝 실험 (본 문서 §4)** |
| P3 | Android native audio + 동일 API |
| P4 | 크로스 디바이스 memory sync (콜드패스) |

---

## 3. Cascaded V1 구현 체크리스트
1. Android/Web: streaming STT (또는 OS SpeechRecognizer) + EOU/VAD
2. emotion: heuristic 또는 경량 SER → `USER_EMOTION` 주입
3. Agent: 기존 Rotom prompt + Dex FACTS + L1 session (+ 이후 memories)
4. streaming TTS: 문장 단위 즉시 합성, style=`electric_device|bright_guide|machine_pulse`
5. barge-in: speaking 중 mic → stop TTS → LISTENING
6. 정책 배지: `pre_device_preview` → `cascaded_v1` 단계 표기
7. 벤치: TTFA, WER(한국어), 주관 자연스러움, IP 혼동 설문(공식 성우와 구분되는지)

감정 태그 스키마(서베이와 동일):
```json
{
  "user_emotion": {"label": "curious", "valence": 0.4, "arousal": 0.6, "confidence": 0.72},
  "reply_emotion": {"label": "encouraging", "style": "electric_device"},
  "policy": {"official_mimicry": false}
}
```

---

## 4. LLaMA-Omni2 0.5B 튜닝 실험 계획 (확정 반영)

### 4.1 목표
- **연구/데모:** 소형 modular SpeechLM이 로토무 **말투·보이스 채널**에 얼마나 가까운지 측정.
- **비목표:** 제품 메인 엔진, Android 핫패스 대체, Dex 지식 주입, 공식 성우 음색 복제.

### 4.2 시작점
- 체크포인트: `ICTNLP/LLaMA-Omni2-0.5B-Bilingual` (EN+ZH; EN-only보다 우선)
- 구조: Whisper-large-v3 encoder → adapter → Qwen2.5-0.5B → CosyVoice2 계열 TTS LM + flow/vocoder
- 원 학습: 200K 멀티턴 S2S, Stage I(a)/I(b)/II (논문 ACL 2025)
- 코드: https://github.com/ictnlp/LLaMA-Omni2 (추론 중심; 학습은 논문 레시피 재현)
- **라이선스 주의:** 모델 **비상업(학술 전용)**. 상용 배포 전 `fengyang@ict.ac.cn` 상업 라이선스 필요. InstructS2S 계열 데이터도 CC BY-NC 성격 → **실험 전용 격리**.

### 4.3 가능성 평가 (스레드 결론 그대로)
| 목표 | 가능성 | 메모 |
| --- | --- | --- |
| 말투/페르소나 | 중 | KR 텍스트+음성 페어 수천~수만 |
| 독자 보이스 | 중~상 | 풀 FT보다 CosyVoice 보이스 프롬프트/클로닝 우선 |
| 한국어 입·출력 | 중하 | 공식 KR 미지원. Whisper 이해≠출력을 한국어로 정렬 |
| Dex FACTS | 낮음 | 0.5B에 지식 주입 금지. RAG sidechannel |
| 감정/끼어들기 | 낮~중 | 논문도 감정 스타일 한계 명시 |
| Android 온디바이스 | 낮음 | “0.5B”여도 Whisper-large-v3+Cosy2로 실제 스택 무거움 |

### 4.4 실험 루트 (최소 → 확장)
```text
E0. 추론 스모크
  - 0.5B-Bilingual Gradio/local infer
  - Cosy2 decoder로 wav 생성
  - 지연·품질 베이스라인 기록

E1. 데이터 (자체 합성만)
  - 한국어 Rotom 멀티턴 텍스트 (페르소나 바이블 준수, FACTS 샘플 포함/제외 분리)
  - 허용 라이선스 TTS로 user/assistant 음성 합성
  - assistant 보이스 = 단일 electric_device 프롬프트 고정
  - 규모: 파일럿 3k–10k 턴 → 본실험 수십 k+

E2. 학습
  - Stage I(a) LoRA: adapter + LLM (페르소나·한국어)
  - 필요 시 Stage I(b)/II: TTS LM / gate
  - Dex 문장을 “암기”시키지 말고, sidechannel 평가 세트 별도

E3. 평가
  - 말투 일치(인간 평가), KR 발음/자연스러움, TTFA
  - FACTS 준수율: transcript를 Agent+Dex에 넣었을 때 vs Omni2 단독 답변
  - IP 혼동: “공식 로토무/정주원 성우처럼 들리는가?” → 목표=아니오

E4. 제품 연결 (성공 시에도)
  - Omni2는 옵트인 GPU voice channel만
  - transcript → 기존 Agent (Dex grounding)
  - 실패/라이선스 문제 시 Cascaded degrade
```

### 4.5 성공/중단 기준
**계속(Go):**
- 학술/연구 격리 환경에서 E0–E2 재현 가능
- 말투 주관 점수 ≥ 기준선(템플릿 TTS 대비 개선)
- FACTS는 sidechannel로 ≥ 템플릿 경로와 동등

**중단(No-Go):**
- 상업 라이선스 확보 불가 + 제품 배포 필요
- 한국어 출력 품질이 cascaded보다 명백히 열위
- 공식 성우/캐릭터 혼동 리스크가 UX 설문에서 높음
- VRAM/지연이 연구 서버에서도 비실용

### 4.6 자원 가정
- GPU: 단일 소비자/워크스테이션급으로 0.5B LoRA 실험 가능 범위 (원작은 4×L40 규모로 시리즈 학습)
- 스토리지: 체크포인트 + Cosy2 + Whisper-large-v3 + 합성 음성 데이터
- 운영: Cloudflare/모바일 핫패스에 올리지 않음

---

## 5. 사용자 메모리 (교차 참조)
- “3000건” = **기억 유닛(hard cap)** 권장 해석.
- SQLite + score eviction + L0~L3 계층.
- 상세 스키마·eviction·dual retrieve: `OpenS2S_감정STS_및_멀티턴메모리_서베이.md` §3.

---

## 6. 한국어 로토무 연기 연구 → 프롬프트 반영 원칙
- 조사 대상: 애니메이션 한국어 더빙의 로토무 도감 연기 패턴(팬/위키 기술, 공개 인터뷰·클립 설명).
- 한국어판 로토무 도감 성우로 널리 기록된 이름: **정주원** (SM~; 일본 나미카와 다이스케에 대응).
- **프롬프트에는 성우 이름·음색·특정 테이크를 복제하지 않는다.**
- 반영하는 것은 **추상화된 연기/말투 기능**(설명 선점, 짧은 호흡, 어미 습관, 호기심, 서포터 정체성 등).
- 상세 추상화 표: `data/rotom_character.md` §3.1, `app/agents/pokedex_agent/prompts/rotom.py`.

---

## 7. 단계 로드맵 (음성)
| Phase | 내용 | 상태 |
| --- | --- | --- |
| V0 | Browser TTS preview + 정책 API | 현재 |
| V1 | Cascaded emotion STS + TTFA/barge-in 게이트 | 계획 |
| V1b | Android native cascaded audio | 계획 |
| V2a | OpenS2S 옵트인 | 계획 |
| V2b | Moshi 옵트인 (풀듀플렉스 데모) | 계획 |
| V2c | LLaMA-Omni2-0.5B 실험 E0–E3 | **계획 반영** |
| V3 | 제품 음성 = Cascaded 고정, GPU는 feature flag | 계획 |

---

## 8. 리스크·열린 질문
1. OpenS2S/Moshi/Omni2 GPU를 누가 호스팅할지 (홈서버 vs 연구실).
2. Omni2 상업 라이선스 확보 여부.
3. 한국어 SER/TTS 품질 벤치 데이터셋.
4. 3000건 = 메모리 유닛 확정 여부 (서베이는 유닛 권장).
5. Cascaded TTFA 1.5s가 저사양 기기에서 달성 가능한지.

## 9. 참고 링크
- Moshi: https://github.com/kyutai-labs/moshi , arXiv:2410.00037
- OpenS2S: https://github.com/CASIA-LM/OpenS2S , arXiv:2507.05177
- LLaMA-Omni2: https://github.com/ictnlp/LLaMA-Omni2 , arXiv:2505.02625
- LLaMA-Omni2-0.5B-Bilingual: https://huggingface.co/ICTNLP/LLaMA-Omni2-0.5B-Bilingual
- InstructS2S / Multiturn Speech Conversations (연구 데이터, NC 주의)
- DuplexCascade (cascaded full-duplex 연구): arXiv:2603.09180
- 내부: `내부_전용_보이스_자산_운영안.md`

## 10. 변경 이력

| 수정일자 | 수정자 | 변경 대상 문서 | 수정 요약 | 반영 상태 |
| :-- | :-- | :-- | :-- | :-- |
| 2026-07-28 17:47 +09:00 | Cursor | `docs/specs/음성_STS_실시간대화_및_Omni2실험_계획.md` | 스레드 논의(Moshi/소형STS/Cascaded실시간/Omni2튜닝실험) 전량 문서화 | 완료 |
