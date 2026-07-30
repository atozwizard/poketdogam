package com.twentyflags.poketdogam

import android.Manifest
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.test.rule.GrantPermissionRule
import org.junit.Rule
import org.junit.Test
import org.junit.rules.RuleChain

class CameraFlowTest {
    private val permissionRule = GrantPermissionRule.grant(Manifest.permission.CAMERA)
    private val composeRule = createAndroidComposeRule<MainActivity>()

    @get:Rule
    val rules: RuleChain = RuleChain.outerRule(permissionRule).around(composeRule)

    @Test
    fun cameraPreviewAndCaptureButtonAreVisibleTogether() {
        composeRule.onNodeWithTag("camera_preview").assertIsDisplayed()
        composeRule.onNodeWithTag("capture_button").assertIsDisplayed()
    }
}
