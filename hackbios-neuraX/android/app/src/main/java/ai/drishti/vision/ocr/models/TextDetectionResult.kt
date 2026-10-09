package ai.drishti.vision.ocr.models

import android.graphics.PointF
import android.graphics.RectF

/**
 * Structured detection result returned by the PP-OCRv4 DBNet text detector.
 *
 * @property polygon 4-point quadrilateral bounding polygon in original unscaled camera frame coordinates.
 * @property boundingBox Minimum axis-aligned bounding box enclosing the polygon.
 * @property score Detection confidence score (box average probability, [0.0..1.0]).
 * @property timestampMs Frame capture timestamp in milliseconds.
 * @property orientation Estimated orientation angle in degrees (0 for horizontal, 90, 180, 270).
 */
data class TextDetectionResult(
    val polygon: List<PointF>,
    val boundingBox: RectF,
    val score: Float,
    val timestampMs: Long = System.currentTimeMillis(),
    val orientation: Float = 0.0f
) {
    init {
        require(polygon.size >= 4) { "Polygon must contain at least 4 vertices, found ${polygon.size}" }
    }

    val width: Float
        get() = boundingBox.width()

    val height: Float
        get() = boundingBox.height()

    val centerX: Float
        get() = boundingBox.centerX()

    val centerY: Float
        get() = boundingBox.centerY()

    val area: Float
        get() = boundingBox.width() * boundingBox.height()

    companion object {
        fun fromPoints(points: List<PointF>, score: Float, timestampMs: Long = System.currentTimeMillis()): TextDetectionResult {
            var minX = Float.MAX_VALUE
            var minY = Float.MAX_VALUE
            var maxX = Float.MIN_VALUE
            var maxY = Float.MIN_VALUE

            for (p in points) {
                if (p.x < minX) minX = p.x
                if (p.x > maxX) maxX = p.x
                if (p.y < minY) minY = p.y
                if (p.y > maxY) maxY = p.y
            }

            val box = RectF(minX, minY, maxX, maxY)
            return TextDetectionResult(
                polygon = points,
                boundingBox = box,
                score = score,
                timestampMs = timestampMs
            )
        }
    }
}
