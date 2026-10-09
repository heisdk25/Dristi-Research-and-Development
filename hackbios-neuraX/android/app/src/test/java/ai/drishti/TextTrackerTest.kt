package ai.drishti

import android.graphics.PointF
import android.graphics.RectF
import ai.drishti.vision.ocr.models.TextDetectionResult
import ai.drishti.vision.ocr.models.TrackState
import ai.drishti.vision.ocr.tracker.TextTracker
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class TextTrackerTest {

    private lateinit var tracker: TextTracker

    @Before
    fun setUp() {
        tracker = TextTracker(
            minIou = 0.35f,
            minHitsToConfirm = 2,
            maxLostFrames = 3,
            smoothingAlpha = 0.7f
        )
    }

    private fun makeDetection(left: Float, top: Float, right: Float, bottom: Float, score: Float = 0.9f): TextDetectionResult {
        val points = listOf(
            PointF(left, top),
            PointF(right, top),
            PointF(right, bottom),
            PointF(left, bottom)
        )
        return TextDetectionResult(
            polygon = points,
            boundingBox = RectF(left, top, right, bottom),
            score = score
        )
    }

    @Test
    fun `initial detection creates tentative track`() {
        val det = makeDetection(100f, 100f, 250f, 150f)
        val tracks = tracker.update(listOf(det), 1000L)

        assertEquals(1, tracks.size)
        val track = tracks[0]
        assertEquals(TrackState.TENTATIVE, track.state)
        assertEquals(1, track.hits)
        assertEquals(0, track.misses)
        assertEquals(1L, track.trackId)
    }

    @Test
    fun `consecutive matching detection confirms tentative track`() {
        val det1 = makeDetection(100f, 100f, 250f, 150f)
        tracker.update(listOf(det1), 1000L)

        // Frame 2: slightly shifted detection with high IoU
        val det2 = makeDetection(102f, 101f, 252f, 151f)
        val tracks = tracker.update(listOf(det2), 1066L)

        assertEquals(1, tracks.size)
        val track = tracks[0]
        assertEquals(TrackState.CONFIRMED, track.state)
        assertEquals(2, track.hits)
        assertEquals(0, track.misses)
    }

    @Test
    fun `unmatched confirmed track transitions to lost and then terminates`() {
        val det1 = makeDetection(100f, 100f, 250f, 150f)
        tracker.update(listOf(det1), 1000L)
        tracker.update(listOf(det1), 1066L) // Confirmed

        // 1st miss -> LOST
        val tracks1 = tracker.update(emptyList(), 1133L)
        assertEquals(1, tracks1.size)
        assertEquals(TrackState.LOST, tracks1[0].state)
        assertEquals(1, tracks1[0].misses)

        // 2nd miss -> still LOST
        tracker.update(emptyList(), 1200L)
        // 3rd miss -> still LOST
        tracker.update(emptyList(), 1266L)
        // 4th miss (> maxLostFrames) -> purged / TERMINATED
        val tracks4 = tracker.update(emptyList(), 1333L)
        assertEquals(0, tracks4.size)
    }

    @Test
    fun `distinct text boxes receive separate track IDs`() {
        val boxA = makeDetection(50f, 50f, 150f, 80f)
        val boxB = makeDetection(50f, 200f, 200f, 240f)

        val tracks = tracker.update(listOf(boxA, boxB), 1000L)
        assertEquals(2, tracks.size)
        assertNotEquals(tracks[0].trackId, tracks[1].trackId)
    }
}
