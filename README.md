# 포켓도감 Local Scan PoC

카드의 이름은 OCR로, 인형·캐릭터의 외형은 로컬 이미지 임베딩으로 분석하고,
두 신호를 결합한 Top-3에서 정확한 폼을 확정하는 비상업 평가용 PoC입니다.

## 현재 범위

- macOS 웹 PoC: OCR + MediaPipe 임베딩 → Top-3 폼 확정 → 상세·근거 낭독 → 로컬 컬렉션
- Android: CameraX → bundled Korean ML Kit + MediaPipe → Top-3 폼 확정 → 상세·기기 TTS
- 시각 PoC: 1–9세대 1,025종, 전세대 참조 임베딩 4,969개
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

`http://127.0.0.1:8000`에서 시작합니다. 스캔 렌즈의 `카메라 켜기`를 누르면
같은 렌즈 안에 실시간 후면 카메라가 표시되고, `사진 촬영`을 누르면 촬영본이
미리보기에 고정됩니다. 사용자가 촬영본을 확인한 뒤 `촬영 이미지 분석`을
눌러야 OCR과 외형 후보 결합이 시작됩니다. 브라우저 카메라를 사용할 수 없는
환경은 `갤러리에서 선택`으로 복구합니다.

전 세대 도감과 1세대 전체 시각 인덱스를 함께 갱신하는 권장 명령은 다음과
같습니다. 수집→임베딩→strict 검증을 통과한 뒤에만 세 파일을 교체합니다.

```bash
uv run --extra vision python scripts/build_local_dex/collector.py --source pokeapi --fetch
```

## 품질 게이트

```bash
bash scripts/quality_gate.sh
```

Android 단위테스트, lint, Debug APK, 계측 테스트 APK, R8 Release AAB는 다음
명령으로 검증합니다.

```bash
cd android
./gradlew testDebugUnitTest lintDebug assembleDebug assembleDebugAndroidTest bundleRelease
```

품질 평가는 엔지니어링 통합 실행과 제품 인식 승인을 분리합니다. 코드·UI·API
통합 테스트는 실행할 수 있지만, 실제 제품 경로와 필드 증거를 포함한 모든 영역이
95점 이상일 때만 `system_test_authorized=true`로 제품 승인을 허용합니다.

```bash
uv run python scripts/evaluate_quality_score.py --require-95
```

macOS 합성 이미지 OCR 벤치는 별도로 실행합니다.

```bash
uv run python scripts/benchmark_image_ocr.py --limit 30
```

1세대 238폼 시각 인식의 변형 홀드아웃은 다음 명령으로 재생성합니다.

```bash
uv run --extra vision python scripts/benchmark_visual_recognition.py
```

714건 결과는 폼 Top-3 93.70%이며 카메라 구도 93.28%, 부분 가림 92.86%,
스튜디오 94.96%입니다. 이는 임시 간접 참조 이미지에 배경·회전·밝기·블러·
가림을 적용한 합성 회귀 결과이며 실물 성능으로 간주하지 않습니다.

2026-08-04 현재 오픈 라이선스·개인정보 검토를 통과한 실물 파일럿은
91장·28종·20명입니다. 실제 제품 경로의 fused Top-3는 9.89%이고, 이미
사진이 있는 종만 대상으로 한 LOO 물리 프로토타입도 69.23%입니다.
**실물 90%는 아직 달성하거나 주장하지 않습니다.** 원본은 `data/raw/`에만
두고 Git·웹·Android·제품 자산에는 포함하지 않습니다.

전세대 파생 벤치도 조건을 구분합니다. 세대 힌트를 준 실험실 검색은 Top-3
91.80%지만 제품 UI처럼 세대 힌트 없이 1–9세대를 한 번에 찾는 공개 탐색은
69.63%입니다. 또한 실제로 평가한 매체는 `in_game_transform` 1종뿐이며,
카드·인형·굿즈 등 7종은 수집 가능한 라벨 목록이지 정확도 인증 범위가 아닙니다.

재현 명령과 출처 명세는 [실물 인식 파일럿](data/vision/README.md)에 있습니다.
2026-08-04 구현 체크리스트는 DB·인프라·UIUX·자동화 테스트에서 각각
95점 이상을 충족하지만, 검증된 필드 인식 점수는 13.3/100입니다. 가중
종합점수는 65.3/100입니다. 엔지니어링 통합 실행은 PASS지만 제품 인식 인증과
Full system authorization, MVP/Production은 `No-Go`입니다.
