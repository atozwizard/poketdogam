# Android PoC vertical slice

This module is the offline Android path for the validated PoC:

1. CameraX still capture.
2. Bundled Korean ML Kit Text Recognition v2.
3. Local read-only `dex.sqlite` matching.
4. Top candidate confirmation and detail display.
5. Temporary capture deletion after OCR.

The build task copies only the validated root `data/dex.sqlite` into generated
assets. Official images, audio, flavor text, network APIs, and product-license
assets are not included.

Prerequisites: Android SDK 37, Build Tools 36.0.0, JDK 17, and Gradle 9.5.
This workspace currently has JDK but no Android SDK, so device build verification
must run in Android Studio or CI before the Android gate can be marked complete.
