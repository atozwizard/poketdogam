# 포켓도감 Local Scan PoC

카드의 이름은 OCR로, 인형·캐릭터의 외형은 로컬 이미지 임베딩으로 분석하고,
두 신호를 결합한 Top-3에서 정확한 폼을 확정하는 비상업 평가용 PoC입니다.

## 현재 범위

- macOS 웹 PoC: OCR + MediaPipe 임베딩 → Top-3 폼 확정 → 상세·근거 낭독 → 로컬 컬렉션
- Android: CameraX → bundled Korean ML Kit + MediaPipe → Top-3 폼 확정 → 상세·기기 TTS
- 시각 PoC: 1세대 전체 151종, 현재 정규화된 238폼에 참조 임베딩 1개씩
- 시각 추론: 전체 프레임 + 중앙 68%/56% 크롭의 3뷰 최고 점수로 배경 영향을 완화
- 도감: 정식 번호 1,025종 + 공식 발표·번호 미정 3종, 전체 1,354폼
- 데이터: 종/폼/타입/스탯/진화 조건 같은 간접 사실 필드만 사용
- 미포함: 원본 참조 이미지, 공식 음성, flavor text, 유료 API, 사용자 이미지 저장

데이터 사용 범위는 `poc_noncommercial_evaluation`이며 정식 제품 배포 라이선스는
PoC/MVP 승인 후 별도 신청하는 전제입니다. 현재 결과는 정식 라이선스를 대체하지
않습니다.

## 실행

```bash
uv sync --extra vision
LOCAL_LLM_PROVIDER=template uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`http://127.0.0.1:8000`에서 이미지 또는 이름 검색으로 시작합니다.

전 세대 도감과 1세대 전체 시각 인덱스를 함께 갱신하는 권장 명령은 다음과
같습니다. 수집→임베딩→strict 검증을 통과한 뒤에만 세 파일을 교체합니다.

```bash
uv run --extra vision python scripts/build_local_dex/collector.py --source pokeapi --fetch
```

## 품질 게이트

```bash
bash scripts/quality_gate.sh
```

macOS 합성 이미지 OCR 벤치는 별도로 실행합니다.

```bash
uv run python scripts/benchmark_image_ocr.py --limit 30
```

1세대 238폼 시각 인식의 변형 홀드아웃은 다음 명령으로 재생성합니다.

```bash
uv run --extra vision python scripts/benchmark_visual_recognition.py
```

714건 결과는 폼 Top-3 94.54%이며 카메라 구도 93.70%, 부분 가림 94.54%,
스튜디오 95.38%입니다. 이는 임시 간접 참조 이미지에 배경·회전·밝기·블러·
가림을 적용한 합성 회귀 결과이며 실물 성능으로 간주하지 않습니다.

2026-07-30에는 Openverse에서 수정 허용 CC 메타데이터를 가진 사용자 촬영
후보 69건을 내려받고, 원 출처 라이선스와 개인정보를 재검토해 68건을 별도
실물 파일럿으로 측정했습니다. 9종·5명 촬영자에 편중된 이 표본에서 현재 제품
경로 Top-3는 2.94%, 현장 사진 프로토타입을 학습/평가로 나눈 실험은
79.41%였습니다. **실물 90%는 아직 달성하거나 주장하지 않습니다.** 원본은
`data/raw/`에만 두고 Git·웹·Android·제품 자산에는 포함하지 않습니다.

재현 명령과 출처 명세는 [실물 인식 파일럿](data/vision/README.md)에 있습니다.
현재 [PO 95점 품질 게이트](docs/specs/PO_95_품질게이트.md) 재평가는 87/100이며,
1세대 151종·촬영자 분리 실물 게이트 전까지 MVP/Production은 `No-Go`입니다.
