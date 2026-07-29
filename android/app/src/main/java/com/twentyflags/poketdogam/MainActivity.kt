package com.twentyflags.poketdogam

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
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
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
    val repository = remember { DexRepository(context) }
    var hasPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED
        )
    }
    var candidates by remember { mutableStateOf(emptyList<DexCandidate>()) }
    var detail by remember { mutableStateOf<DexDetail?>(null) }
    var status by remember { mutableStateOf("카드 이름이 선명하게 보이도록 맞춰주세요.") }
    val cameraController = remember {
        LifecycleCameraController(context).apply {
            setEnabledUseCases(CameraController.IMAGE_CAPTURE)
        }
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> hasPermission = granted }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFFFFF8EA))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("포켓도감 PoC", style = MaterialTheme.typography.headlineMedium)
            Text("비상업 평가 · 이미지 원본 미저장", color = Color(0xFF765A59))
        }
        item {
            if (!hasPermission) {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("카드 스캔에는 카메라 권한이 필요합니다.")
                        Button(onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) }) {
                            Text("카메라 권한 허용")
                        }
                    }
                }
            } else {
                AndroidView(
                    factory = {
                        PreviewView(it).apply {
                            controller = cameraController
                            cameraController.bindToLifecycle(context as ComponentActivity)
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(360.dp),
                )
            }
        }
        item {
            Text(status)
            Button(
                enabled = hasPermission,
                onClick = {
                    status = "이미지에서 이름을 읽는 중…"
                    captureAndRecognize(
                        activity = context as ComponentActivity,
                        controller = cameraController,
                        onText = { text ->
                            candidates = repository.match(text)
                            detail = null
                            status = if (candidates.isEmpty()) {
                                "후보를 찾지 못했습니다. 다시 촬영해 주세요."
                            } else {
                                "후보가 맞는지 확인해 주세요."
                            }
                        },
                        onError = { message -> status = message },
                    )
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("촬영하고 이름 분석")
            }
        }
        items(candidates) { candidate ->
            OutlinedButton(
                onClick = { detail = repository.detail(candidate.formId) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    "No.${candidate.pokemonId.toString().padStart(4, '0')} " +
                        "${candidate.nameKo} · ${candidate.types.joinToString("/")}"
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
                        selected.stats.forEach { (label, value) ->
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text(label)
                                Text(value.toString())
                            }
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
    onText: (String) -> Unit,
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
                val input = InputImage.fromFilePath(activity, android.net.Uri.fromFile(temporaryImage))
                recognizer.process(input)
                    .addOnSuccessListener { onText(it.text) }
                    .addOnFailureListener { onError("문자를 읽지 못했습니다. 다시 촬영해 주세요.") }
                    .addOnCompleteListener {
                        recognizer.close()
                        temporaryImage.delete()
                    }
            }

            override fun onError(exception: ImageCaptureException) {
                temporaryImage.delete()
                onError("촬영에 실패했습니다. 카메라 상태를 확인해 주세요.")
            }
        },
    )
}
