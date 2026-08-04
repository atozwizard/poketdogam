from __future__ import annotations

from pathlib import Path
import argparse
import ast
from contextlib import closing
import json
import sqlite3
import sys

from scripts.build_local_dex.artifacts import verify_artifact_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_SCORE = 95.0
ALL_SPECIES_TARGET = 94.0
WILD_ACCURACY_TARGET = 95.0


def evaluate() -> dict[str, object]:
    db_path = PROJECT_ROOT / "data" / "dex.sqlite"
    meta_path = PROJECT_ROOT / "data" / "dex.meta.json"
    visual_index = PROJECT_ROOT / "data" / "vision" / "gen1_visual_index.json"
    visual_model = PROJECT_ROOT / "data" / "vision" / "mobilenet_v3_small.tflite"
    with closing(sqlite3.connect(db_path)) as conn:
        species = int(conn.execute("select count(*) from pokemon_species").fetchone()[0])
        forms = int(conn.execute("select count(*) from pokemon_forms").fetchone()[0])
        gen1_species = int(
            conn.execute("select count(*) from pokemon_species where generation = 1").fetchone()[0]
        )
        gen1_forms = int(
            conn.execute(
                """
                select count(*) from pokemon_forms f
                join pokemon_species s on s.pokemon_id = f.pokemon_id
                where s.generation = 1
                """
            ).fetchone()[0]
        )
        visual_forms = int(
            conn.execute(
                "select count(distinct form_id) from visual_reference_embeddings"
            ).fetchone()[0]
        )
        gen1_visual_forms = int(
            conn.execute(
                """
                select count(distinct v.form_id)
                from visual_reference_embeddings v
                join pokemon_forms f on f.form_id = v.form_id
                join pokemon_species s on s.pokemon_id = f.pokemon_id
                where s.generation = 1
                """
            ).fetchone()[0]
        )
        visual_species = int(
            conn.execute(
                """
                select count(distinct f.pokemon_id)
                from visual_reference_embeddings v
                join pokemon_forms f on f.form_id = v.form_id
                """
            ).fetchone()[0]
        )
        schema_version = int(conn.execute("pragma user_version").fetchone()[0])
        quick_check = str(conn.execute("pragma quick_check").fetchone()[0])
        orphan_count = len(conn.execute("pragma foreign_key_check").fetchall())

    manifest = verify_artifact_manifest(
        meta_path,
        {
            "dex.sqlite": db_path,
            "gen1_visual_index.json": visual_index,
            "mobilenet_v3_small.tflite": visual_model,
        },
    )
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    database_checks = {
        "all_announced_species_loaded": species >= 1028,
        "generation_1_complete": gen1_species == 151,
        "generation_1_forms_indexed": gen1_forms == gen1_visual_forms == 238,
        "schema_versioned": schema_version == 1,
        "sqlite_integrity": quick_check == "ok",
        "foreign_keys_clean": orphan_count == 0,
        "artifact_manifest_valid": manifest["valid"] is True,
        "derivative_data_boundary": metadata.get("derivative_data_only") is True,
        "official_media_excluded": metadata.get("official_media_included") is False,
    }

    ui = (PROJECT_ROOT / "app" / "ui" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "app" / "ui" / "app.js").read_text(encoding="utf-8")
    camera_quality = (PROJECT_ROOT / "app" / "ui" / "camera-quality.js").read_text(encoding="utf-8")
    styles = (PROJECT_ROOT / "app" / "ui" / "styles.css").read_text(encoding="utf-8")
    ocr_tool = (
        PROJECT_ROOT / "app" / "agents" / "pokedex_agent" / "tools" / "tool_ocr_ondevice.py"
    ).read_text(encoding="utf-8")
    android_main = (
        PROJECT_ROOT
        / "android"
        / "app"
        / "src"
        / "main"
        / "java"
        / "com"
        / "twentyflags"
        / "poketdogam"
        / "MainActivity.kt"
    ).read_text(encoding="utf-8")
    ui_checks = {
        "live_camera_in_lens": 'id="cameraPreview"' in ui,
        "explicit_capture_button": 'id="captureButton"' in ui,
        "camera_permission_flow": "navigator.mediaDevices.getUserMedia" in javascript,
        "captured_image_preview": "captureCameraFrame" in javascript,
        "lighting_and_focus_feedback": "PoketdogamCameraQuality" in javascript,
        "gallery_fallback": "갤러리에서 선택" in ui,
        "ranking_score_is_not_probability": "확률이 아닌 비교 점수" in javascript,
        "deletion_failure_is_reported": "로컬 서버의 대화를 삭제하지 못했습니다" in javascript,
        "camera_status_is_live": 'class="lens-readout" aria-live="polite"' in ui,
        "mobile_touch_target": "min-height: 48px" in styles,
        "card_name_band_guide": 'class="name-band"' in ui and "카드명 영역" in ui,
        "card_name_band_ocr": "name_band" in ocr_tool and "nameBandCropBox" in camera_quality,
        "android_card_name_band": "카드명 영역" in android_main,
        "recognition_evidence_separated": (
            'id="productEvidence"' in ui
            and 'id="labEvidence"' in ui
            and 'id="fieldEvidence"' in ui
        ),
        "generation_collection_progress": (
            'id="generationProgress"' in ui
            and "renderGenerationProgress" in javascript
        ),
        "scan_failure_tips": all(
            needle in javascript for needle in ("조명", "70%", "카드명 영역", "배경")
        ),
    }

    scan_route = (PROJECT_ROOT / "app" / "api" / "routes" / "scan.py").read_text(encoding="utf-8")
    main = (PROJECT_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    collector = (
        PROJECT_ROOT / "scripts" / "build_local_dex" / "collector.py"
    ).read_text(encoding="utf-8")
    android_build = (PROJECT_ROOT / "android" / "app" / "build.gradle.kts").read_text(
        encoding="utf-8"
    )
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "quality.yml").read_text(
        encoding="utf-8"
    )
    engineering_checks = {
        "local_only_default": 'host: str = "127.0.0.1"' in (
            PROJECT_ROOT / "app" / "config" / "settings.py"
        ).read_text(encoding="utf-8"),
        "scan_off_event_loop": "run_in_threadpool" in scan_route,
        "scan_capacity_limited": "BoundedSemaphore" in scan_route,
        "decoded_pixel_guard": "MAX_IMAGE_PIXELS" in scan_route,
        "security_headers": "X-Content-Type-Options" in main,
        "liveness_and_readiness": "/health/live" in main and "/health/ready" in main,
        "runtime_metrics": '"/metrics"' in main,
        "atomic_dataset_publish": "os.replace" in collector,
        "android_hash_install": "dex.meta.json" in android_build,
        "android_ci_and_release": "testDebugUnitTest" in workflow and "bundleRelease" in workflow,
    }

    test_counts = _test_counts()
    test_checks = {
        "python_unit_and_integration": test_counts["python"] >= 45,
        "javascript_unit": test_counts["javascript"] >= 2,
        "kotlin_unit": test_counts["kotlin_unit"] >= 2,
        "android_instrumentation": test_counts["android_instrumentation"] >= 1,
        "quality_gate": "quality_gate.sh" in workflow,
        "android_lint": "lintDebug" in workflow,
        "android_test_apk": "assembleDebugAndroidTest" in workflow,
        "dependency_monitoring": (PROJECT_ROOT / ".github" / "dependabot.yml").exists(),
        "system_test_harness": (PROJECT_ROOT / "scripts" / "system_test.sh").exists(),
    }

    field = json.loads(
        (PROJECT_ROOT / "data" / "vision" / "field_benchmark.json").read_text(encoding="utf-8")
    )
    scope = field["scope"]
    field_recall = float(field["aggregate"]["fused_species_recall_at_3"])
    universal_cert_path = (
        PROJECT_ROOT / "data" / "vision" / "universal_recognition_cert.json"
    )
    universal_bench_path = PROJECT_ROOT / "data" / "vision" / "universal_benchmark.json"
    universal = (
        json.loads(universal_cert_path.read_text(encoding="utf-8"))
        if universal_cert_path.exists()
        else {}
    )
    product_recall = float(
        universal.get("product_open_search_species_recall_at_3")
        or universal.get("cross_generation_species_recall_at_3")
        or 0.0
    )
    generation_aided_lab_recall = float(
        universal.get("generation_scoped_lab_species_recall_at_3")
        or universal.get("species_recall_at_3")
        or 0.0
    )
    covered_species = int(universal.get("covered_species") or 0)
    recognizable_samples = int(universal.get("recognizable_samples") or 0)
    evaluated_media_kind_count = int(
        universal.get("evaluated_media_kind_count") or 0
    )
    product_requirements = universal.get("requirements") or {
        "species": 1025,
        "samples": 1025,
        "evaluated_media_kinds": 4,
        "top3_recall": 0.90,
    }
    product_accuracy_progress = min(
        100.0,
        product_recall
        / float(product_requirements.get("top3_recall") or 0.90)
        * 100.0,
    )
    product_coverage_progress = (
        min(
            covered_species
            / max(1, int(product_requirements.get("species") or 1025)),
            recognizable_samples
            / max(1, int(product_requirements.get("samples") or 1025)),
            evaluated_media_kind_count
            / max(
                1,
                int(product_requirements.get("evaluated_media_kinds") or 4),
            ),
        )
        * 100.0
    )
    product_open_search_score = round(
        product_accuracy_progress * 0.7 + product_coverage_progress * 0.3,
        1,
    )
    product_open_search_certified = (
        bool(universal.get("certified"))
        and product_recall >= float(product_requirements.get("top3_recall") or 0.90)
        and evaluated_media_kind_count
        >= int(product_requirements.get("evaluated_media_kinds") or 4)
    )

    field_species = int(scope["covered_species_count"])
    field_creators = int(scope["covered_creator_count"])
    field_samples = int(scope["sample_count"])
    field_requirements = {
        "top3_recall": 0.90,
        "species": 151,
        "creators": 30,
        "samples": 453,
    }
    field_accuracy_progress = min(100.0, field_recall / 0.90 * 100.0)
    field_coverage_progress = (
        min(
            field_species / field_requirements["species"],
            field_creators / field_requirements["creators"],
            field_samples / field_requirements["samples"],
        )
        * 100.0
    )
    field_recognition_score = round(
        field_accuracy_progress * 0.7 + field_coverage_progress * 0.3,
        1,
    )
    wild_accuracy_certified = (
        field_recognition_score >= WILD_ACCURACY_TARGET
        and field_recall >= field_requirements["top3_recall"]
        and field_species >= field_requirements["species"]
        and field_creators >= field_requirements["creators"]
        and field_samples >= field_requirements["samples"]
        and bool(field.get("generation_wide_90_percent_claimable"))
    )

    loo_path = PROJECT_ROOT / "data" / "vision" / "field_loo_physical_experiment.json"
    loo = json.loads(loo_path.read_text(encoding="utf-8")) if loo_path.exists() else {}
    with closing(sqlite3.connect(db_path)) as conn:
        physical_refs = int(
            conn.execute(
                "select count(*) from visual_reference_embeddings "
                "where reference_kind = 'open_license_field_photo_derived'"
            ).fetchone()[0]
        )

    # 전체 포켓몬 종 반영: 텍스트 종 + 시각 폼 커버리지를 94점 목표로 추적
    text_species_progress = min(100.0, species / 1028 * 100.0)
    visual_form_progress = min(100.0, visual_forms / max(1, forms) * 100.0)
    visual_species_progress = min(100.0, visual_species / max(1, species) * 100.0)
    all_species_score = round(
        text_species_progress * 0.4 + visual_form_progress * 0.4 + visual_species_progress * 0.2,
        1,
    )

    scores = {
        "database_data": _check_score(database_checks),
        "engineering_infra": _check_score(engineering_checks),
        "uiux": _check_score(ui_checks),
        "automated_tests": _check_score(test_checks),
        "field_recognition": field_recognition_score,
    }
    overall = round(
        scores["database_data"] * 0.15
        + scores["engineering_infra"] * 0.15
        + scores["uiux"] * 0.15
        + scores["automated_tests"] * 0.15
        + scores["field_recognition"] * 0.40,
        1,
    )
    all_scores_meet_target = (
        all(score >= TARGET_SCORE for score in scores.values())
        and product_open_search_certified
        and wild_accuracy_certified
    )
    mvp_engineering_go = (
        scores["database_data"] >= TARGET_SCORE
        and scores["engineering_infra"] >= TARGET_SCORE
        and scores["uiux"] >= TARGET_SCORE
        and scores["automated_tests"] >= TARGET_SCORE
        and all_species_score >= ALL_SPECIES_TARGET
        and ui_checks["card_name_band_guide"]
        and ui_checks["card_name_band_ocr"]
    )
    return {
        "target": TARGET_SCORE,
        "scores": scores,
        "overall": overall,
        "all_scores_meet_target": all_scores_meet_target,
        "system_test_authorized": all_scores_meet_target,
        "mvp_engineering_go": mvp_engineering_go,
        "wild_accuracy_certification": {
            "score": field_recognition_score,
            "target": WILD_ACCURACY_TARGET,
            "certified": wild_accuracy_certified,
            "mode": "physical_field_generation_1",
            "physical_reference_count": physical_refs,
            "loo_physical_recall_at_3": loo.get("recall_at_3"),
            "loo_generation_wide_claimable": False,
            "universal_benchmark": str(universal_bench_path.relative_to(PROJECT_ROOT))
            if universal_bench_path.exists()
            else None,
            "coverage_gap": {
                "species": max(
                    0,
                    field_requirements["species"] - field_species,
                ),
                "samples": max(
                    0,
                    field_requirements["samples"] - field_samples,
                ),
                "creators": max(
                    0,
                    field_requirements["creators"] - field_creators,
                ),
            },
            "next_actions": [
                "Collect and independently review more physical photos",
                "Rebuild physical references and rerun benchmark_field_photos.py",
                "Keep product UI free of official media; embeddings remain derived-only",
            ],
        },
        "product_open_search_certification": {
            "score": product_open_search_score,
            "target": WILD_ACCURACY_TARGET,
            "certified": product_open_search_certified,
            "species_recall_at_3": product_recall,
            "generation_aided_lab_species_recall_at_3": generation_aided_lab_recall,
            "evaluated_media_kind_count": evaluated_media_kind_count,
            "corpus_media_kind_count": int(
                universal.get("corpus_media_kind_count") or 0
            ),
            "requirements": product_requirements,
            "generation_hint_used": False,
        },
        "all_species_coverage": {
            "score": all_species_score,
            "target": ALL_SPECIES_TARGET,
            "meets_target": all_species_score >= ALL_SPECIES_TARGET,
            "text_species": species,
            "visual_species": visual_species,
            "visual_forms": visual_forms,
            "total_forms": forms,
            "gen1_visual_forms": gen1_visual_forms,
        },
        "field_evidence": {
            "product_open_search_top3_recall": product_recall,
            "generation_aided_lab_top3_recall": generation_aided_lab_recall,
            "field_pilot_top3_recall": field_recall,
            "covered_species": covered_species,
            "recognizable_samples": recognizable_samples,
            "evaluated_media_kind_count": evaluated_media_kind_count,
            "field_covered_species": field_species,
            "field_covered_creators": field_creators,
            "field_eligible_samples": field_samples,
            "field_required": field_requirements,
            "product_required": product_requirements,
        },
        "test_inventory": test_counts,
        "checks": {
            "database_data": database_checks,
            "engineering_infra": engineering_checks,
            "uiux": ui_checks,
            "automated_tests": test_checks,
        },
        "blocking_scores": {
            name: score for name, score in scores.items() if score < TARGET_SCORE
        },
        "blocking_gates": {
            "product_open_search_certification": product_open_search_certified,
            "physical_field_certification": wild_accuracy_certified,
        },
    }


def _check_score(checks: dict[str, bool]) -> float:
    return round(sum(checks.values()) / max(1, len(checks)) * 100.0, 1)


def _test_counts() -> dict[str, int]:
    python_count = 0
    for path in (PROJECT_ROOT / "tests").glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        python_count += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
            for node in ast.walk(tree)
        )
    javascript = (
        PROJECT_ROOT / "tests" / "ui_camera_quality.test.cjs"
    ).read_text(encoding="utf-8").count("test(")
    kotlin_unit = sum(
        path.read_text(encoding="utf-8").count("@Test")
        for path in (PROJECT_ROOT / "android" / "app" / "src" / "test").rglob("*.kt")
    )
    android_instrumentation = sum(
        path.read_text(encoding="utf-8").count("@Test")
        for path in (PROJECT_ROOT / "android" / "app" / "src" / "androidTest").rglob("*.kt")
    )
    return {
        "python": python_count,
        "javascript": javascript,
        "kotlin_unit": kotlin_unit,
        "android_instrumentation": android_instrumentation,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-95", action="store_true")
    parser.add_argument("--require-mvp-engineering-go", action="store_true")
    parser.add_argument("--require-wild-95", action="store_true")
    parser.add_argument("--require-all-species-94", action="store_true")
    parser.add_argument("--require-product-open-search-90", action="store_true")
    args = parser.parse_args()
    result = evaluate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    exit_code = 0
    if args.require_95 and not result["all_scores_meet_target"]:
        exit_code = 2
    if args.require_mvp_engineering_go and not result["mvp_engineering_go"]:
        exit_code = 2
    if args.require_wild_95 and not result["wild_accuracy_certification"]["certified"]:
        exit_code = 2
    if args.require_all_species_94 and not result["all_species_coverage"]["meets_target"]:
        exit_code = 2
    if (
        args.require_product_open_search_90
        and not result["product_open_search_certification"]["certified"]
    ):
        exit_code = 2
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
