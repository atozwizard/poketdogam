package com.twentyflags.poketdogam

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.tts.TextToSpeech
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.view.CameraController
import androidx.camera.view.LifecycleCameraController
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions
import java.io.File
import java.util.Locale
import java.util.concurrent.Executors

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                PoketdogamScreen()
            }
        }
    }
}

@Composable
private fun PoketdogamScreen() {
    val context = LocalContext.current
    val activity = context as ComponentActivity
    val repository = remember { DexRepository(context) }
    val visualMatcher = remember { VisualMatcher(context, repository) }
    val preferences = remember { context.getSharedPreferences("poketdogam", 0) }
    var autoNarration by remember {
        mutableStateOf(preferences.getBoolean("auto_narration", false))
    }
    var ttsReady by remember { mutableStateOf(false) }
    val textToSpeech = remember {
        TextToSpeech(context) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
        }
    }
    DisposableEffect(textToSpeech, visualMatcher) {
        onDispose {
            textToSpeech.stop()
            textToSpeech.shutdown()
            visualMatcher.close()
        }
    }

    var hasPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED
        )
    }
    var candidates by remember { mutableStateOf(emptyList<DexCandidate>()) }
    var detail by remember { mutableStateOf<DexDetail?>(null) }
    var status by remember { mutableStateOf("카드·인형·캐릭터가 화면에 잘 보이도록 맞춰주세요.") }
    val cameraController = remember {
        LifecycleCameraController(context).apply {
            setEnabledUseCases(CameraController.IMAGE_CAPTURE)
        }
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> hasPermission = granted }

    fun speak(selected: DexDetail) {
        if (!ttsReady) {
            status = "기기 음성 엔진을 준비 중입니다."
            return
        }
        textToSpeech.language = Locale.KOREAN
        textToSpeech.setPitch(1.14f)
        textToSpeech.setSpeechRate(1.04f)
        textToSpeech.speak(
            buildNarration(selected),
            TextToSpeech.QUEUE_FLUSH,
            null,
            "poketdogam-${selected.formId}",
        )
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFFFFF8EA))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("포켓도감 PoC", style = MaterialTheme.typography.headlineMedium)
            Text("1세대 151종·238폼 외형 후보 · 전체 세대 도감 · 이미지 원본 미저장", color = Color(0xFF765A59))
        }
        item {
            if (!hasPermission) {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("이미지 인식에는 카메라 권한이 필요합니다.")
                        Button(onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) }) {
                            Text("카메라 권한 허용")
                        }
                    }
                }
            } else {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(260.dp),
                ) {
                    AndroidView(
                        factory = {
                            PreviewView(it).apply {
                                implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                                controller = cameraController
                                cameraController.bindToLifecycle(activity)
                            }
                        },
                        modifier = Modifier.fillMaxSize(),
                    )
                    Box(
                        modifier = Modifier
                            .align(Alignment.Center)
                            .fillMaxWidth(0.56f)
                            .aspectRatio(1f)
                            .border(3.dp, Color(0xFFFFD54F)),
                    )
                    Text(
                        "인형·캐릭터를 노란 프레임의 70% 이상 채워주세요",
                        color = Color.White,
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .background(Color(0xB3000000))
                            .padding(horizontal = 10.dp, vertical = 6.dp),
                    )
                }
            }
        }
        item {
            Text(status)
            Button(
                enabled = hasPermission,
                onClick = {
                    status = "OCR과 외형 임베딩을 결합하는 중…"
                    captureAndRecognize(
                        activity = activity,
                        controller = cameraController,
                        repository = repository,
                        visualMatcher = visualMatcher,
                        onCandidates = { result ->
                            candidates = result
                            detail = null
                            status = if (candidates.isEmpty()) {
                                "후보를 찾지 못했습니다. 다시 촬영해 주세요."
                            } else {
                                "Top-${candidates.size} 후보입니다. 정확한 폼을 선택해 주세요."
                            }
                        },
                        onError = { message -> status = message },
                    )
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("촬영하고 이름+외형 분석")
            }
        }
        items(candidates) { candidate ->
            OutlinedButton(
                onClick = {
                    detail = repository.detail(candidate.formId)
                    status = "${candidate.nameKo} ${candidate.formName} 폼을 확정했습니다."
                    detail?.let { if (autoNarration) speak(it) }
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                val number = if (candidate.pokemonId > 0) {
                    "No.${candidate.pokemonId.toString().padStart(4, '0')}"
                } else {
                    "공식 발표·번호 미정"
                }
                val evidence = candidate.evidence.joinToString("+")
                Text(
                    "$number ${candidate.nameKo} · ${candidate.formName} · " +
                        "${candidate.types.joinToString("/")} · $evidence " +
                        "${(candidate.confidence * 100).toInt()}%"
                )
            }
        }
        detail?.let { selected ->
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(selected.nameKo, style = MaterialTheme.typography.headlineSmall)
                        Text("${selected.nameEn} · ${selected.generation}세대 · ${selected.formName}")
                        Text(selected.types.joinToString(" / "))
                        Text(
                            "약점: " + selected.weaknesses.joinToString(", ") {
                                "${it.type} ×${it.multiplier}"
                            }
                        )
                        selected.stats.forEach { (label, value) ->
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text(label)
                                Text(value.toString())
                            }
                        }
                        Button(
                            onClick = { speak(selected) },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("로토무 설명 듣기")
                        }
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text("정확한 폼 확정 후 자동 낭독")
                            Switch(
                                checked = autoNarration,
                                onCheckedChange = { checked ->
                                    autoNarration = checked
                                    preferences.edit().putBoolean("auto_narration", checked).apply()
                                },
                            )
                        }
                    }
                }
            }
        }
    }
}

private fun captureAndRecognize(
    activity: ComponentActivity,
    controller: LifecycleCameraController,
    repository: DexRepository,
    visualMatcher: VisualMatcher,
    onCandidates: (List<DexCandidate>) -> Unit,
    onError: (String) -> Unit,
) {
    val temporaryImage = File.createTempFile("poketdogam-", ".jpg", activity.cacheDir)
    val output = ImageCapture.OutputFileOptions.Builder(temporaryImage).build()
    controller.takePicture(
        output,
        ContextCompat.getMainExecutor(activity),
        object : ImageCapture.OnImageSavedCallback {
            override fun onImageSaved(result: ImageCapture.OutputFileResults) {
                val recognizer = TextRecognition.getClient(KoreanTextRecognizerOptions.Builder().build())
                val executor = Executors.newSingleThreadExecutor()
                var ocrCandidates: List<DexCandidate>? = null
                var visualCandidates: List<DexCandidate>? = null

                fun finishIfReady() {
                    val ocr = ocrCandidates ?: return
                    val visual = visualCandidates ?: return
                    temporaryImage.delete()
                    executor.shutdown()
                    onCandidates(repository.fuse(ocr, visual, limit = 3))
                }

                executor.execute {
                    val visual = runCatching { visualMatcher.match(temporaryImage, limit = 5) }
                        .getOrDefault(emptyList())
                    ContextCompat.getMainExecutor(activity).execute {
                        visualCandidates = visual
                        finishIfReady()
                    }
                }

                val input = InputImage.fromFilePath(activity, android.net.Uri.fromFile(temporaryImage))
                recognizer.process(input)
                    .addOnSuccessListener { result ->
                        ocrCandidates = repository.match(result.text, limit = 5)
                    }
                    .addOnFailureListener {
                        ocrCandidates = emptyList()
                    }
                    .addOnCompleteListener {
                        recognizer.close()
                        finishIfReady()
                    }
            }

            override fun onError(exception: ImageCaptureException) {
                temporaryImage.delete()
                onError("촬영에 실패했습니다. 카메라 상태를 확인해 주세요.")
            }
        },
    )
}
