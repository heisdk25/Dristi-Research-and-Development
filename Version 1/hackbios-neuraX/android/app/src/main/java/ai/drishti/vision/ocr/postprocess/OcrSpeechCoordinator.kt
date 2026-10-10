package ai.drishti.vision.ocr.postprocess

import android.util.Log
import ai.drishti.audio.LocalTTS
import ai.drishti.vision.ocr.models.TrackedText

/**
 * Coordinates text delivery between the video OCR pipeline and LocalTTS.
 *
 * Implements:
 * 1. Non-blocking queued speech (flush = false) for continuous reading.
 * 2. Instant cancellation (muteAndClear) when mode exits or obstacle alerts interrupt.
 * 3. Rate-limiting to ensure natural reading cadence without audio overlap.
 */
class OcrSpeechCoordinator(
    private val localTTS: LocalTTS,
    private val readingOrderEngine: TextReadingOrderEngine = TextReadingOrderEngine()
) {

    private val tag = "OcrSpeechCoordinator"
    private var lastSpokenTimeMs = 0L
    private val minSpeechIntervalMs = 1500L

    fun onTracksUpdated(tracks: List<TrackedText>, nowMs: Long = System.currentTimeMillis()): String? {
        if (nowMs - lastSpokenTimeMs < minSpeechIntervalMs) {
            return null
        }

        val novelContent = readingOrderEngine.extractNovelReadingContent(tracks, nowMs)
        if (!novelContent.isNullOrBlank()) {
            lastSpokenTimeMs = nowMs
            Log.i(tag, "Dispatching novel OCR text to LocalTTS: \"$novelContent\"")
            localTTS.speak(novelContent, flush = false)
            return novelContent
        }

        return null
    }

    fun muteAndClear() {
        Log.i(tag, "Muting OCR speech and resetting reading history.")
        readingOrderEngine.clearHistory()
        localTTS.stop()
    }
}
