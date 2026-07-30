from __future__ import annotations

from pathlib import Path
import argparse
import ast
import json
import sqlite3
import sys

from scripts.build_local_dex.artifacts import verify_artifact_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_SCORE = 95.0


def evaluate() -> dict[str, object]:
    db_path = PROJECT_ROOT / "data" / "dex.sqlite"
    meta_path = PROJECT_ROOT / "data" / "dex.meta.json"
    visual_index = PROJECT_ROOT / "data" / "vision" / "gen1_visual_index.json"
    visual_model = PROJECT_ROOT / "data" / "vision" / "mobilenet_v3_small.tflite"
    with sqlite3.connect(db_path) as conn:
        species = int(conn.execute("select count(*) from pokemon_species").fetchone()[0])
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
        "generation_1_forms_indexed": gen1_forms == visual_forms == 238,
        "schema_versioned": schema_version == 1,
        "sqlite_integrity": quick_check == "ok",
        "foreign_keys_clean": orphan_count == 0,
        "artifact_manifest_valid": manifest["valid"] is True,
        "derivative_data_boundary": metadata.get("derivative_data_only") is True,
        "official_media_excluded": metadata.get("official_media_included") is False,
    }

    ui = (PROJECT_ROOT / "app" / "ui" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "app" / "ui" / "app.js").read_text(encoding="utf-8")
    styles = (PROJECT_ROOT / "app" / "ui" / "styles.css").read_text(encoding="utf-8")
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
    }

    field = json.loads(
        (PROJECT_ROOT / "data" / "vision" / "field_benchmark.json").read_text(encoding="utf-8")
    )
    scope = field["scope"]
    recall = float(field["aggregate"]["fused_species_recall_at_3"])
    accuracy_progress = min(100.0, recall / 0.90 * 100.0)
    coverage_progress = min(
        int(scope["covered_species_count"]) / 151,
        int(scope["covered_creator_count"]) / 30,
        int(scope["sample_count"]) / 453,
    ) * 100.0
    recognition_score = round(accuracy_progress * 0.7 + coverage_progress * 0.3, 1)

    scores = {
        "database_data": _check_score(database_checks),
        "engineering_infra": _check_score(engineering_checks),
        "uiux": _check_score(ui_checks),
        "automated_tests": _check_score(test_checks),
        "field_recognition": recognition_score,
    }
    overall = round(
        scores["database_data"] * 0.15
        + scores["engineering_infra"] * 0.15
        + scores["uiux"] * 0.15
        + scores["automated_tests"] * 0.15
        + scores["field_recognition"] * 0.40,
        1,
    )
    all_scores_meet_target = all(score >= TARGET_SCORE for score in scores.values())
    return {
        "target": TARGET_SCORE,
        "scores": scores,
        "overall": overall,
        "all_scores_meet_target": all_scores_meet_target,
        "system_test_authorized": all_scores_meet_target,
        "field_evidence": {
            "production_top3_recall": recall,
            "covered_species": int(scope["covered_species_count"]),
            "covered_creators": int(scope["covered_creator_count"]),
            "eligible_samples": int(scope["sample_count"]),
            "required": {"top3_recall": 0.90, "species": 151, "creators": 30, "samples": 453},
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
    args = parser.parse_args()
    result = evaluate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.require_95 and not result["all_scores_meet_target"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
