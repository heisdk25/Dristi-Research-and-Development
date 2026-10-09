package ai.drishti

import android.graphics.PointF
import android.graphics.RectF
import ai.drishti.vision.ocr.models.TrackState
import ai.drishti.vision.ocr.models.TrackedText
import ai.drishti.vision.ocr.postprocess.TextReadingOrderEngine
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class TextReadingOrderEngineTest {

    private lateinit var engine: TextReadingOrderEngine

    @Before
    fun setUp() {
        engine = TextReadingOrderEngine(
            deduplicationThreshold = 0.70f,
            spokenHistoryExpiryMs = 10000L
        )
    }

    private fun makeTrack(id: Long, text: String, left: Float, top: Float, right: Float, bottom: Float): TrackedText {
        val points = listOf(
            PointF(left, top),
            PointF(right, top),
            PointF(right, bottom),
            PointF(left, bottom)
        )
        return TrackedText(
            trackId = id,
            polygon = points,
            boundingBox = RectF(left, top, right, bottom),
            confidence = 0.95f,
            state = TrackState.CONFIRMED,
            recognizedText = text
        )
    }

    @Test
    fun `reading order clusters into top-to-bottom and left-to-right`() {
        // Line 1: "PHARMACY" (left) and "OPEN" (right) around Y=100
        val word1 = makeTrack(1L, "PHARMACY", 50f, 95f, 180f, 135f)
        val word2 = makeTrack(2L, "OPEN", 220f, 98f, 310f, 138f)

        // Line 2: "DAILY" (left) and "24 HOURS" (right) around Y=200
        val word3 = makeTrack(3L, "DAILY", 60f, 195f, 150f, 235f)
        val word4 = makeTrack(4L, "24 HOURS", 180f, 192f, 320f, 232f)

        // Shuffle input list to test sorting
        val shuffled = listOf(word4, word1, word3, word2)
        val clusteredLines = engine.clusterIntoReadingLines(shuffled)

        assertEquals(2, clusteredLines.size)
        // First line: PHARMACY, OPEN
        assertEquals("PHARMACY", clusteredLines[0][0].recognizedText)
        assertEquals("OPEN", clusteredLines[0][1].recognizedText)

        // Second line: DAILY, 24 HOURS
        assertEquals("DAILY", clusteredLines[1][0].recognizedText)
        assertEquals("24 HOURS", clusteredLines[1][1].recognizedText)
    }

    @Test
    fun `deduplication filters repeated phrases within history window`() {
        val t1 = makeTrack(1L, "Exit 4B", 100f, 100f, 250f, 140f)
        val novelText1 = engine.extractNovelReadingContent(listOf(t1), 1000L)
        assertNotNull(novelText1)
        assertTrue(novelText1!!.contains("Exit 4B"))

        // Same track on next video frame: already spoken, must return null
        val novelText2 = engine.extractNovelReadingContent(listOf(t1), 1100L)
        assertNull(novelText2)

        // New track with identical wording: deduplicated by history window
        val t2 = makeTrack(2L, "Exit 4B", 102f, 101f, 252f, 141f)
        val novelText3 = engine.extractNovelReadingContent(listOf(t2), 1200L)
        assertNull(novelText3)
    }

    @Test
    fun `similarity metric accurately detects near duplicates`() {
        val simHigh = engine.computeSimilarity("Pharmacy Open 24h", "Pharmacy Open 24 Hours")
        assertTrue(simHigh > 0.65f)

        val simLow = engine.computeSimilarity("Pharmacy Open", "Bus Stop Metro")
        assertTrue(simLow < 0.2f)
    }
}
