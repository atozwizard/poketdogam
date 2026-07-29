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

        self.assertIn("text-recognition-korean:16.0.1", build_file)
        self.assertIn("camera-view:1.6.1", build_file)
        self.assertIn("../data/dex.sqlite", build_file)
        self.assertIn("android.permission.CAMERA", manifest)
        self.assertNotIn("android.permission.INTERNET", manifest)
        self.assertIn("temporaryImage.delete()", activity)


if __name__ == "__main__":
    unittest.main()
