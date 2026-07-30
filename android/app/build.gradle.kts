plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.twentyflags.poketdogam"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.twentyflags.poketdogam"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0-poc"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildFeatures {
        compose = true
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }

    sourceSets["main"].assets.srcDir(
        layout.buildDirectory.get().dir("generated/dexAssets").asFile
    )
}

val generatedDexAssets = layout.buildDirectory.dir("generated/dexAssets")

val syncVerifiedDex by tasks.registering(Copy::class) {
    from(rootProject.projectDir.resolve("../data/dex.sqlite"))
    from(rootProject.projectDir.resolve("../data/vision/mobilenet_v3_small.tflite"))
    from(rootProject.projectDir.resolve("../data/vision/gen1_visual_index.json"))
    into(generatedDexAssets)
    doFirst {
        val requiredAssets = listOf(
            rootProject.projectDir.resolve("../data/dex.sqlite"),
            rootProject.projectDir.resolve("../data/vision/mobilenet_v3_small.tflite"),
            rootProject.projectDir.resolve("../data/vision/gen1_visual_index.json"),
        )
        require(requiredAssets.all { it.exists() }) {
            "Run the validated Dex collector and Generation 1 visual index builder before Android."
        }
    }
}

tasks.named("preBuild").configure {
    dependsOn(syncVerifiedDex)
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.06.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("androidx.camera:camera-camera2:1.6.1")
    implementation("androidx.camera:camera-lifecycle:1.6.1")
    implementation("androidx.camera:camera-view:1.6.1")
    implementation("androidx.exifinterface:exifinterface:1.4.1")
    implementation("com.google.mlkit:text-recognition-korean:16.0.1")
    implementation("com.google.mediapipe:tasks-vision:0.10.29")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
