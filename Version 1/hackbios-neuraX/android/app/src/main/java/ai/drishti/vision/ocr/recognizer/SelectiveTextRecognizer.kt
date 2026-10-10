package ai.drishti.vision.ocr.recognizer

import android.graphics.Bitmap
import android.graphics.RectF
import android.util.Log
import ai.drishti.vision.ocr.models.OcrFramePacket
import ai.drishti.vision.ocr.models.TrackedText
import kotlin.math.max
import kotlin.math.min

/**
 * Selective Recognition Engine for video text reading.
 *
 * Prevents redundant recognition computations across continuous video frames by:
 * 1. Filtering only tracks in CONFIRMED state that either have no text or underwent significant scale change.
 * 2. Capping maximum recognition inferences per video frame (e.g. max 3 regions per frame) to prevent CPU starvation.
 * 3. Cropping high-resolution text ROIs directly from uncompressed original camera frames with boundary clamping.
 * 4. Storing recognized text directly onto persistent TrackedText instances.
 */
class SelectiveTextRecognizer(
    val recognizer: IPpOcrRecognizer,
    private val maxRecognitionsPerFrame: Int = 3
) {

    private val tag = "SelectiveRecognizer"

    fun processTracks(tracks: List<TrackedText>, packet: OcrFramePacket): List<TrackedText> {
        val nowMs = packet.timestampMs
        val fullBitmap = packet.bitmap

        if (fullBitmap.isRecycled || fullBitmap.width <= 0 || fullBitmap.height <= 0) {
            return tracks
        }

        // 1. Identify tracks requiring recognition sorted by area descending (read prominent headlines first)
        val candidateTracks = tracks
            .filter { it.needsRecognition(nowMs) }
            .sortedByDescending { it.boundingBox.width() * it.boundingBox.height() }
            .take(maxRecognitionsPerFrame)

        if (candidateTracks.isEmpty()) {
            return tracks
        }

        Log.d(tag, "Selected ${candidateTracks.size} / ${tracks.size} tracks for selective recognition")

        // 2. Execute recognition on candidate crops
        for (track in candidateTracks) {
            val box = track.boundingBox
            val pad = 4

            val cropLeft = max(0, (box.left - pad).toInt())
            val cropTop = max(0, (box.top - pad).toInt())
            val cropRight = min(fullBitmap.width, (box.right + pad).toInt())
            val cropBottom = min(fullBitmap.height, (box.bottom + pad).toInt())

            val cropWidth = cropRight - cropLeft
            val cropHeight = cropBottom - cropTop

            if (cropWidth < 8 || cropHeight < 6) continue

            try {
                val cropped = Bitmap.createBitmap(fullBitmap, cropLeft, cropTop, cropWidth, cropHeight)
                val (recognizedText, confidence) = recognizer.recognize(cropped)
                cropped.recycle()

                if (recognizedText.isNotBlank()) {
                    track.recognizedText = recognizedText.trim()
                    track.recognitionConfidence = confidence
                    track.lastRecognizedBounds = RectF(track.boundingBox)
                    track.lastRecognizedTimestampMs = nowMs
                    Log.i(tag, "Track #${track.trackId} recognized: \"${track.recognizedText}\" (conf=$confidence)")
                }
            } catch (e: Exception) {
                Log.e(tag, "Failed to crop or recognize track #${track.trackId}", e)
            }
        }

        return tracks
    }

    fun close() {
        recognizer.close()
    }
}
