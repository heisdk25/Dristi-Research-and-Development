package ai.drishti.vision.ocr.pipeline

import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import ai.drishti.audio.LocalTTS
import ai.drishti.camera.CameraSource
import ai.drishti.vision.ocr.detector.IPpOcrDetector
import ai.drishti.vision.ocr.detector.PpOcrV4Detector
import ai.drishti.vision.ocr.models.OcrFramePacket
import ai.drishti.vision.ocr.models.TrackedText
import ai.drishti.vision.ocr.postprocess.OcrSpeechCoordinator
import ai.drishti.vision.ocr.recognizer.IPpOcrRecognizer
import ai.drishti.vision.ocr.recognizer.PpOcrV4Recognizer
import ai.drishti.vision.ocr.recognizer.SelectiveTextRecognizer
import ai.drishti.vision.ocr.tracker.ITextTracker
import ai.drishti.vision.ocr.tracker.TextTracker
import kotlinx.coroutines.CoroutineScope

/**
 * Master Video OCR Pipeline for Project Drishti Version 2.0.
 *
 * Implements the full edge stream pipeline:
 * ESP32-CAM live stream → Android frame pipeline → PP-OCRv4 text detector → lightweight text tracker
 * → selective PP-OCRv4 text recognizer → text post-processing → existing local text-to-speech → user's ear.
 */
class VideoOcrPipeline(
    private val context: Context,
    private val scope: CoroutineScope,
    private val localTTS: LocalTTS,
    customDetector: IPpOcrDetector? = null,
    customTracker: ITextTracker? = null,
    customRecognizer: IPpOcrRecognizer? = null
) {

    private val tag = "VideoOcrPipeline"

    // Subsystems
    val detector: IPpOcrDetector = customDetector ?: PpOcrV4Detector(context)
    val tracker: ITextTracker = customTracker ?: TextTracker()
    private val recognizerEngine: IPpOcrRecognizer = customRecognizer ?: PpOcrV4Recognizer(context)
    val selectiveRecognizer: SelectiveTextRecognizer = SelectiveTextRecognizer(recognizerEngine)
    val speechCoordinator: OcrSpeechCoordinator = OcrSpeechCoordinator(localTTS)

    private val frameDispatcher = BoundedFrameDispatcher(scope) { packet ->
        processFrameInternal(packet)
    }

    var isRunning: Boolean = false
        private set

    /**
     * UI / Debug callback providing tracked text regions with status for live overlay rendering.
     */
    var onTracksUpdated: ((List<TrackedText>) -> Unit)? = null

    /**
     * Callback notifying when novel text has been spoken.
     */
    var onTextSpoken: ((String) -> Unit)? = null

    fun start() {
        if (isRunning) return
        isRunning = true
        tracker.reset()
        frameDispatcher.start()
        val diag = getPipelineDiagnostics()
        Log.i(tag, "VideoOcrPipeline started. Diagnostics: $diag")
    }

    /**
     * Reports runtime status of detection and recognition inference engines.
     */
    fun getPipelineDiagnostics(): Map<String, Any> {
        val detBackend = (detector as? PpOcrV4Detector)?.activeBackend ?: "CUSTOM_DETECTOR"
        val recBackend = ((selectiveRecognizer.recognizer as? PpOcrV4Recognizer))?.activeBackend ?: "CUSTOM_RECOGNIZER"
        return mapOf(
            "detectorBackend" to detBackend,
            "recognizerBackend" to recBackend,
            "isOfflineReady" to (detBackend.contains("ONNX") && recBackend.contains("ONNX")),
            "isRunning" to isRunning
        )
    }

    /**
     * Ingests a new camera frame from ESP32-CAM or phone camera.
     * Uses latest-frame-wins buffering: if inference is busy, intermediate frames are dropped.
     */
    fun feedFrame(bitmap: Bitmap, source: CameraSource, timestampMs: Long = System.currentTimeMillis()) {
        if (!isRunning) return
        val packet = OcrFramePacket(
            bitmap = bitmap,
            timestampMs = timestampMs,
            source = source
        )
        frameDispatcher.dispatch(packet)
    }

    private fun processFrameInternal(packet: OcrFramePacket) {
        val t0 = System.currentTimeMillis()

        // 1. Stage A: PP-OCRv4 Text Detection (DBNet on 320x320 letterbox)
        val detections = detector.detect(packet)
        val tDet = System.currentTimeMillis() - t0

        // 2. Stage B: Spatial-Temporal Text Tracking across frames
        val updatedTracks = tracker.update(detections, packet.timestampMs)
        val tTrack = System.currentTimeMillis() - (t0 + tDet)

        // 3. Stage C: Selective Text Recognition (PP-OCRv4 SVTR/LCNet on confirmed/novel tracks only)
        val recognizedTracks = selectiveRecognizer.processTracks(updatedTracks, packet)
        val tRec = System.currentTimeMillis() - (t0 + tDet + tTrack)

        // 4. Update UI / Debug overlay
        onTracksUpdated?.invoke(recognizedTracks)

        // 5. Stage D: Post-processing reading order & novel text delivery to LocalTTS
        val spoken = speechCoordinator.onTracksUpdated(recognizedTracks, packet.timestampMs)
        if (spoken != null) {
            onTextSpoken?.invoke(spoken)
        }

        val totalMs = System.currentTimeMillis() - t0
        Log.d(tag, "OCR frame cycle: det=${tDet}ms, track=${tTrack}ms, rec=${tRec}ms, total=${totalMs}ms (${detections.size} det, ${recognizedTracks.size} tracks)")
    }

    fun stop() {
        if (!isRunning) return
        isRunning = false
        frameDispatcher.stop()
        speechCoordinator.muteAndClear()
        tracker.reset()
        Log.i(tag, "VideoOcrPipeline stopped.")
    }

    fun close() {
        stop()
        detector.close()
        selectiveRecognizer.close()
        Log.i(tag, "VideoOcrPipeline closed and resources released.")
    }
}
