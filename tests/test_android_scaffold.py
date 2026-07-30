from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AndroidScaffoldTest(unittest.TestCase):
    def test_android_vertical_slice_is_offline_and_bundles_verified_dex(self) -> None:
        build_file = (PROJECT_ROOT / "android/app/build.gradle.kts").read_text(encoding="utf-8")
        manifest = (PROJECT_ROOT / "android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        activity = (
            PROJECT_ROOT
            / "android/app/src/main/java/com/twentyflags/poketdogam/MainActivity.kt"
        ).read_text(encoding="utf-8")
        visual_matcher = (
            PROJECT_ROOT
            / "android/app/src/main/java/com/twentyflags/poketdogam/VisualMatcher.kt"
        ).read_text(encoding="utf-8")
        narrator = (
            PROJECT_ROOT
            / "android/app/src/main/java/com/twentyflags/poketdogam/RotomNarrator.kt"
        ).read_text(encoding="utf-8")

        self.assertIn("text-recognition-korean:16.0.1", build_file)
        self.assertIn("tasks-vision:0.10.29", build_file)
        self.assertIn("camera-view:1.6.1", build_file)
        self.assertIn("../data/dex.sqlite", build_file)
        self.assertIn("../data/vision/gen1_visual_index.json", build_file)
        self.assertIn("../data/vision/mobilenet_v3_small.tflite", build_file)
        self.assertIn("android.permission.CAMERA", manifest)
        self.assertIn(
            'android.permission.INTERNET" tools:node="remove"',
            manifest,
        )
        self.assertIn(
            'android.permission.ACCESS_NETWORK_STATE" tools:node="remove"',
            manifest,
        )
        self.assertIn("temporaryImage.delete()", activity)
        self.assertIn("repository.fuse", activity)
        self.assertIn("TextToSpeech", activity)
        self.assertIn("reference_count", visual_matcher)
        self.assertIn("buildNarration", narrator)


if __name__ == "__main__":
    unittest.main()
