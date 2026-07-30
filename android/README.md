# Android PoC vertical slice

This module is the offline Android path for the validated PoC:

1. CameraX still capture.
2. Bundled Korean ML Kit Text Recognition v2 plus MediaPipe MobileNetV3 embedding.
3. EXIF correction and full/68%/56% center-view visual matching.
4. OCR/visual score fusion into a maximum of three candidates.
5. Explicit exact-form confirmation and local read-only `dex.sqlite` detail.
6. Grounded type/weakness/evolution narration through Android TextToSpeech.
7. Temporary capture deletion after both recognizers finish.

The build task copies the validated Dex, the 1.3MB Generation 1 derived numeric
embedding index (151 species/238 forms), and its public MobileNetV3 runtime model
into generated assets. Reference images, official audio, flavor text, network
APIs, and product-license assets are not included.

Prerequisites: Android SDK Platform 37.0, Build Tools 36.0.0+, JDK 17+, and the
committed Gradle wrapper.

```bash
cd android
./gradlew assembleDebug
```
