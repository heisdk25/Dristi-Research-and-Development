package ai.drishti.vision.ocr.models

import android.graphics.PointF
import android.graphics.RectF
import kotlin.math.abs

enum class TrackState {
    TENTATIVE,
    CONFIRMED,
    LOST,
    TERMINATED
}

/**
 * Represents a persistent temporal text track across video frames.
 */
data class TrackedText(
    val trackId: Long,
    var polygon: List<PointF>,
    var boundingBox: RectF,
    var confidence: Float,
    var state: TrackState = TrackState.TENTATIVE,
    var hits: Int = 1,
    var misses: Int = 0,
    val firstSeenTimestampMs: Long = System.currentTimeMillis(),
    var lastSeenTimestampMs: Long = System.currentTimeMillis(),
    var recognizedText: String? = null,
    var recognitionConfidence: Float? = null,
    var isSpoken: Boolean = false,
    var lastRecognizedBounds: RectF? = null,
    var lastRecognizedTimestampMs: Long = 0L
) {
    /**
     * Determines whether this track needs PP-OCRv4 text recognition.
     *
     * Selective Recognition Policy:
     * 1. Only CONFIRMED tracks are recognized (never waste compute on jittery TENTATIVE noise).
     * 2. Unrecognized tracks: trigger immediately upon confirmation.
     * 3. Re-recognition triggers:
     *    - Significant scale/perspective change (> 30% area difference, e.g. user moved closer).
     *    - Periodic stabilization refresh (> 5000ms elapsed since last recognition).
     */
    fun needsRecognition(nowMs: Long = System.currentTimeMillis()): Boolean {
        if (state != TrackState.CONFIRMED) return false

        // 1. Initial recognition
        if (recognizedText == null) return true

        // 2. Significant scale change (zooming in or approaching text resolves finer characters)
        val lastBounds = lastRecognizedBounds
        if (lastBounds != null) {
            val prevArea = lastBounds.width() * lastBounds.height()
            val currArea = boundingBox.width() * boundingBox.height()
            if (prevArea > 0f) {
                val areaChangeRatio = abs(currArea - prevArea) / prevArea
                if (areaChangeRatio > 0.35f) {
                    return true
                }
            }
        }

        // 3. Periodic refresh for long-standing view
        if (nowMs - lastRecognizedTimestampMs > 5000L) {
            return true
        }

        return false
    }

    /**
     * Updates track with a matched detection, applying Exponential Moving Average (EMA) smoothing.
     */
    fun updateWithDetection(detection: TextDetectionResult, alpha: Float = 0.7f) {
        hits++
        misses = 0
        lastSeenTimestampMs = detection.timestampMs
        confidence = detection.score

        if (state == TrackState.LOST) {
            state = TrackState.CONFIRMED
        }

        // EMA smoothing for bounding box to prevent reading jitter
        val smoothedLeft = alpha * detection.boundingBox.left + (1f - alpha) * boundingBox.left
        val smoothedTop = alpha * detection.boundingBox.top + (1f - alpha) * boundingBox.top
        val smoothedRight = alpha * detection.boundingBox.right + (1f - alpha) * boundingBox.right
        val smoothedBottom = alpha * detection.boundingBox.bottom + (1f - alpha) * boundingBox.bottom

        boundingBox.set(smoothedLeft, smoothedTop, smoothedRight, smoothedBottom)
        polygon = detection.polygon
    }

    fun markMissed() {
        misses++
        if (misses > 0 && state == TrackState.CONFIRMED) {
            state = TrackState.LOST
        }
    }
}
