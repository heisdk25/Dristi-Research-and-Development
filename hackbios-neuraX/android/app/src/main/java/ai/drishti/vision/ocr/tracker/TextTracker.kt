package ai.drishti.vision.ocr.tracker

import android.graphics.RectF
import ai.drishti.vision.ocr.models.TextDetectionResult
import ai.drishti.vision.ocr.models.TrackState
import ai.drishti.vision.ocr.models.TrackedText
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Lightweight spatial-temporal text tracker.
 *
 * Associates detected text regions across consecutive video frames to:
 * 1. Filter out transient visual flicker, motion blur, and false positives.
 * 2. Maintain stable track IDs for selective recognition.
 * 3. Provide coordinate smoothing via Exponential Moving Average (EMA).
 */
class TextTracker(
    private val minIou: Float = 0.35f,
    private val minHitsToConfirm: Int = 2,
    private val maxLostFrames: Int = 3,
    private val smoothingAlpha: Float = 0.7f
) : ITextTracker {

    private var nextTrackId: Long = 1L
    private val activeTracks = mutableListOf<TrackedText>()

    override fun update(detections: List<TextDetectionResult>, timestampMs: Long): List<TrackedText> {
        val unmatchedDetections = detections.indices.toMutableSet()
        val unmatchedTracks = activeTracks.indices.toMutableSet()

        // 1. Calculate Pairwise Affinity Matrix: IoU minus normalized center distance penalty
        val matches = mutableListOf<Pair<Int, Int>>() // Pair(trackIdx, detectionIdx)

        if (activeTracks.isNotEmpty() && detections.isNotEmpty()) {
            val scoreMatrix = mutableListOf<Triple<Int, Int, Float>>() // trackIdx, detIdx, score

            for (tIdx in activeTracks.indices) {
                val track = activeTracks[tIdx]
                if (track.state == TrackState.TERMINATED) continue

                for (dIdx in detections.indices) {
                    val det = detections[dIdx]
                    val iou = computeIoU(track.boundingBox, det.boundingBox)
                    if (iou >= minIou) {
                        val centerDistPenalty = computeCenterDistPenalty(track.boundingBox, det.boundingBox)
                        val affinity = iou - (0.2f * centerDistPenalty)
                        scoreMatrix.add(Triple(tIdx, dIdx, affinity))
                    }
                }
            }

            // Greedy bipartite matching sorted by affinity score descending
            scoreMatrix.sortByDescending { it.third }

            val matchedTracks = mutableSetOf<Int>()
            val matchedDets = mutableSetOf<Int>()

            for ((tIdx, dIdx, _) in scoreMatrix) {
                if (tIdx !in matchedTracks && dIdx !in matchedDets) {
                    matchedTracks.add(tIdx)
                    matchedDets.add(dIdx)
                    matches.add(Pair(tIdx, dIdx))
                    unmatchedTracks.remove(tIdx)
                    unmatchedDetections.remove(dIdx)
                }
            }
        }

        // 2. Update Matched Tracks
        for ((tIdx, dIdx) in matches) {
            val track = activeTracks[tIdx]
            val det = detections[dIdx]

            track.updateWithDetection(det, smoothingAlpha)

            // Confirm tentative track once minimum hits threshold reached
            if (track.state == TrackState.TENTATIVE && track.hits >= minHitsToConfirm) {
                track.state = TrackState.CONFIRMED
            }
        }

        // 3. Handle Unmatched Existing Tracks (Coasting / Lost / Terminated)
        for (tIdx in unmatchedTracks) {
            val track = activeTracks[tIdx]
            track.markMissed()

            if (track.misses > maxLostFrames) {
                track.state = TrackState.TERMINATED
            }
        }

        // 4. Create New Tracks for Unmatched Detections
        for (dIdx in unmatchedDetections) {
            val det = detections[dIdx]
            val newTrack = TrackedText(
                trackId = nextTrackId++,
                polygon = det.polygon,
                boundingBox = RectF(det.boundingBox),
                confidence = det.score,
                state = TrackState.TENTATIVE,
                hits = 1,
                misses = 0,
                firstSeenTimestampMs = timestampMs,
                lastSeenTimestampMs = timestampMs
            )
            // If detection is already very large and confident, accelerate confirmation
            if (det.score > 0.85f && det.area > 2000f) {
                // Keep tentative for at least 1 confirmation frame to ensure temporal stability
            }
            activeTracks.add(newTrack)
        }

        // 5. Purge Terminated Tracks
        activeTracks.removeAll { it.state == TrackState.TERMINATED }

        return activeTracks.toList()
    }

    override fun getActiveTracks(): List<TrackedText> = activeTracks.toList()

    override fun reset() {
        activeTracks.clear()
        nextTrackId = 1L
    }

    companion object {
        fun computeIoU(b1: RectF, b2: RectF): Float {
            val interLeft = max(b1.left, b2.left)
            val interTop = max(b1.top, b2.top)
            val interRight = min(b1.right, b2.right)
            val interBottom = min(b1.bottom, b2.bottom)

            val interWidth = max(0f, interRight - interLeft)
            val interHeight = max(0f, interBottom - interTop)
            val interArea = interWidth * interHeight

            if (interArea <= 0f) return 0f

            val area1 = b1.width() * b1.height()
            val area2 = b2.width() * b2.height()
            val unionArea = area1 + area2 - interArea

            return if (unionArea > 0f) interArea / unionArea else 0f
        }

        fun computeCenterDistPenalty(b1: RectF, b2: RectF): Float {
            val c1x = b1.centerX()
            val c1y = b1.centerY()
            val c2x = b2.centerX()
            val c2y = b2.centerY()

            val maxDim = max(max(b1.width(), b1.height()), max(b2.width(), b2.height()))
            if (maxDim <= 0f) return 1.0f

            val dx = (c1x - c2x) / maxDim
            val dy = (c1y - c2y) / maxDim
            return min(1.0f, sqrt(dx * dx + dy * dy))
        }
    }
}
