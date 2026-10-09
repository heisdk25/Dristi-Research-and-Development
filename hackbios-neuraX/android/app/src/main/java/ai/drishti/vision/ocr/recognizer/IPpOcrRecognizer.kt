package ai.drishti.vision.ocr.recognizer

import android.graphics.Bitmap

/**
 * Interface abstraction for text recognition engines.
 */
interface IPpOcrRecognizer {
    /**
     * Recognizes text characters within a cropped text ROI bitmap.
     * @return Pair of recognized text string and average character confidence score [0.0..1.0].
     */
    fun recognize(croppedBitmap: Bitmap): Pair<String, Float>

    /**
     * Releases recognizer memory and sessions.
     */
    fun close()
}
