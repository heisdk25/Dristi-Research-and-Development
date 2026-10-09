package ai.drishti.vision.ocr.detector

import ai.drishti.vision.ocr.models.OcrFramePacket
import ai.drishti.vision.ocr.models.TextDetectionResult

/**
 * Common abstraction for optical character recognition text detectors.
 */
interface IPpOcrDetector {
    /**
     * Executes text detection on an unscaled camera frame packet.
     * Returns detected text polygons in original unscaled camera frame coordinates.
     */
    fun detect(packet: OcrFramePacket): List<TextDetectionResult>

    /**
     * Releases model buffers and native resources.
     */
    fun close()
}
