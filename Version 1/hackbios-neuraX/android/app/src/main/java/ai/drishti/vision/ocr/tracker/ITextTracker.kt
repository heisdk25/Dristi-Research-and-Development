package ai.drishti.vision.ocr.tracker

import ai.drishti.vision.ocr.models.TextDetectionResult
import ai.drishti.vision.ocr.models.TrackedText

/**
 * Interface abstraction for video text region tracking.
 */
interface ITextTracker {
    /**
     * Associates new frame detections with existing active text tracks.
     * Updates track lifecycles, states, and coordinates.
     *
     * @param detections List of text detections from the current frame.
     * @param timestampMs Frame timestamp.
     * @return List of current active tracks.
     */
    fun update(detections: List<TextDetectionResult>, timestampMs: Long): List<TrackedText>

    /**
     * Returns all currently active tracks.
     */
    fun getActiveTracks(): List<TrackedText>

    /**
     * Clears all tracking state and resets monotonic ID counter.
     */
    fun reset()
}
