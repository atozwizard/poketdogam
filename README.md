# 포켓도감 Local Scan PoC

카드 이미지에서 포켓몬 이름을 OCR로 읽고, 로컬 SQLite 도감에서 후보·폼·진화
조건·타입 상성을 확인하는 비상업 평가용 PoC입니다.

## 현재 범위

- macOS 웹 PoC: Vision OCR → Top-3 → 상세 → 근거 템플릿 대화 → 로컬 컬렉션
- Android 수직 슬라이스: CameraX → bundled Korean ML Kit → read-only Dex → Top-3 → 상세
- 데이터: 종/폼/타입/스탯/진화 조건 같은 간접 사실 필드만 사용
- 미포함: 공식 이미지, 공식 음성, flavor text, 유료 API, 사용자 이미지 저장

데이터 사용 범위는 `poc_noncommercial_evaluation`이며 정식 제품 배포 라이선스는
PoC/MVP 승인 후 별도 신청하는 전제입니다. 현재 결과는 정식 라이선스를 대체하지
않습니다.

## 실행

```bash
uv sync
LOCAL_LLM_PROVIDER=template uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`http://127.0.0.1:8000`에서 이미지 또는 이름 검색으로 시작합니다.

## 품질 게이트

```bash
bash scripts/quality_gate.sh
```

macOS 합성 이미지 OCR 벤치는 별도로 실행합니다.

```bash
uv run python scripts/benchmark_image_ocr.py --limit 30
```

합성 렌더 이미지 결과는 실물 카드 성능으로 간주하지 않습니다. 실물 카드
30→100장과 Android 실기기 검증은 정식 MVP Go/No-Go의 별도 필수 게이트입니다.

현재 웹 PoC 구현 완성도는 [PO 95점 품질 게이트](docs/specs/PO_95_품질게이트.md)
기준 97/100입니다. 이는 이해관계자 사용성 평가 진입 판정이며, 정식 MVP 또는
Production 출시 승인은 아닙니다.
