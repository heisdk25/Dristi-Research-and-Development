package ai.drishti.vision.ocr.models

import android.graphics.Bitmap
import ai.drishti.camera.CameraSource

/**
 * Encapsulates an incoming camera frame with temporal and provenance metadata.
 */
data class OcrFramePacket(
    val bitmap: Bitmap,
    val timestampMs: Long = System.currentTimeMillis(),
    val source: CameraSource = CameraSource.ESP32_WIFI,
    val originalWidth: Int = bitmap.width,
    val originalHeight: Int = bitmap.height
)
