package ai.drishti

import android.graphics.Bitmap
import android.graphics.PointF
import android.graphics.RectF
import ai.drishti.camera.CameraSource
import ai.drishti.vision.ocr.models.OcrFramePacket
import ai.drishti.vision.ocr.models.TrackState
import ai.drishti.vision.ocr.models.TrackedText
import ai.drishti.vision.ocr.recognizer.IPpOcrRecognizer
import ai.drishti.vision.ocr.recognizer.SelectiveTextRecognizer
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class SelectiveTextRecognizerTest {

    private lateinit var selectiveRecognizer: SelectiveTextRecognizer
    private var mockRecognizeCount = 0

    private val fakeRecognizer = object : IPpOcrRecognizer {
        override fun recognize(croppedBitmap: Bitmap): Pair<String, Float> {
            mockRecognizeCount++
            return Pair("RECOGNIZED_TEXT_$mockRecognizeCount", 0.95f)
        }

        override fun close() {}
    }

    @Before
    fun setUp() {
        mockRecognizeCount = 0
        selectiveRecognizer = SelectiveTextRecognizer(fakeRecognizer, maxRecognitionsPerFrame = 2)
    }

    private fun createFakePacket(): OcrFramePacket {
        val bmp = Bitmap.createBitmap(320, 240, Bitmap.Config.ARGB_8888)
        return OcrFramePacket(bmp, 1000L, CameraSource.Esp32Cam)
    }

    private fun createTrack(id: Long, state: TrackState, left: Float, top: Float, right: Float, bottom: Float): TrackedText {
        return TrackedText(
            trackId = id,
            polygon = listOf(PointF(left, top), PointF(right, top), PointF(right, bottom), PointF(left, bottom)),
            boundingBox = RectF(left, top, right, bottom),
            state = state,
            firstSeenTimestampMs = 1000L,
            lastSeenTimestampMs = 1000L,
            hits = if (state == TrackState.CONFIRMED) 2 else 1,
            misses = 0
        )
    }

    @Test
    fun `tentative tracks are not scheduled for recognition`() {
        val tentativeTrack = createTrack(1L, TrackState.TENTATIVE, 10f, 10f, 100f, 40f)
        val packet = createFakePacket()

        val processed = selectiveRecognizer.processTracks(listOf(tentativeTrack), packet)
        assertEquals(0, mockRecognizeCount)
        assertNull(processed[0].recognizedText)
    }

    @Test
    fun `confirmed track without text is recognized`() {
        val confirmedTrack = createTrack(1L, TrackState.CONFIRMED, 10f, 10f, 100f, 40f)
        val packet = createFakePacket()

        val processed = selectiveRecognizer.processTracks(listOf(confirmedTrack), packet)
        assertEquals(1, mockRecognizeCount)
        assertEquals("RECOGNIZED_TEXT_1", processed[0].recognizedText)
        assertEquals(0.95f, processed[0].recognitionConfidence)
    }

    @Test
    fun `max recognitions per frame budget is enforced`() {
        val t1 = createTrack(1L, TrackState.CONFIRMED, 10f, 10f, 100f, 40f) // area 2700
        val t2 = createTrack(2L, TrackState.CONFIRMED, 10f, 50f, 120f, 90f) // area 4400
        val t3 = createTrack(3L, TrackState.CONFIRMED, 10f, 100f, 200f, 150f) // area 9500
        val packet = createFakePacket()

        // maxRecognitionsPerFrame is 2
        val processed = selectiveRecognizer.processTracks(listOf(t1, t2, t3), packet)
        assertEquals(2, mockRecognizeCount)
        // t3 and t2 should be recognized first because of area descending sort
        assertNotNull(t3.recognizedText)
        assertNotNull(t2.recognizedText)
        assertNull(t1.recognizedText)
    }

    @Test
    fun `confirmed track with text is not redundantly recognized unless scale changed`() {
        val t1 = createTrack(1L, TrackState.CONFIRMED, 10f, 10f, 100f, 40f)
        val packet = createFakePacket()

        // 1st cycle: recognized
        selectiveRecognizer.processTracks(listOf(t1), packet)
        assertEquals(1, mockRecognizeCount)

        // 2nd cycle: unchanged bounds -> recognition skipped
        selectiveRecognizer.processTracks(listOf(t1), packet)
        assertEquals(1, mockRecognizeCount) // count should NOT increase!

        // 3rd cycle: significant scale change (more than 30%)
        t1.boundingBox = RectF(10f, 10f, 160f, 70f)
        selectiveRecognizer.processTracks(listOf(t1), packet)
        assertEquals(2, mockRecognizeCount) // re-recognized due to scale change!
    }
}
