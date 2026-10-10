package ai.drishti.vision.ocr.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View
import ai.drishti.vision.ocr.models.TrackState
import ai.drishti.vision.ocr.models.TrackedText

/**
 * Visual debug overlay rendering detected polygons, track IDs, and recognized text
 * directly on top of the camera viewport for developer debugging and sighted caregivers.
 */
class OcrDebugOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    private var trackedItems: List<TrackedText> = emptyList()
    private var frameWidth: Int = 1
    private var frameHeight: Int = 1
    var isOverlayEnabled: Boolean = true

    private val boxPaintConfirmed = Paint().apply {
        color = Color.parseColor("#10B981") // Emerald Green
        style = Paint.Style.STROKE
        strokeWidth = 4f
        isAntiAlias = true
    }

    private val boxPaintTentative = Paint().apply {
        color = Color.parseColor("#F59E0B") // Amber
        style = Paint.Style.STROKE
        strokeWidth = 2.5f
        isAntiAlias = true
    }

    private val textBgPaint = Paint().apply {
        color = Color.parseColor("#CC0F172A") // Semi-transparent dark slate
        style = Paint.Style.FILL
        isAntiAlias = true
    }

    private val textPaint = Paint().apply {
        color = Color.WHITE
        textSize = 28f
        isFakeBoldText = true
        isAntiAlias = true
    }

    private val subTextPaint = Paint().apply {
        color = Color.parseColor("#38BDF8") // Light Cyan
        textSize = 20f
        isAntiAlias = true
    }

    fun updateTracks(tracks: List<TrackedText>, srcWidth: Int = 640, srcHeight: Int = 480) {
        if (!isOverlayEnabled) return
        this.trackedItems = tracks
        this.frameWidth = if (srcWidth > 0) srcWidth else 1
        this.frameHeight = if (srcHeight > 0) srcHeight else 1
        postInvalidate()
    }

    fun clear() {
        this.trackedItems = emptyList()
        postInvalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (!isOverlayEnabled || trackedItems.isEmpty()) return

        val viewW = width.toFloat()
        val viewH = height.toFloat()
        val scaleX = viewW / frameWidth
        val scaleY = viewH / frameHeight

        val path = Path()

        for (track in trackedItems) {
            val poly = track.polygon
            if (poly.size >= 4) {
                path.reset()
                path.moveTo(poly[0].x * scaleX, poly[0].y * scaleY)
                for (i in 1 until poly.size) {
                    path.lineTo(poly[i].x * scaleX, poly[i].y * scaleY)
                }
                path.close()

                val paint = when (track.state) {
                    TrackState.CONFIRMED -> boxPaintConfirmed
                    else -> boxPaintTentative
                }
                canvas.drawPath(path, paint)
            }

            // Draw text banner above box
            val label = track.recognizedText ?: "[Scanning... ID #${track.trackId}]"
            val textX = track.boundingBox.left * scaleX
            val textY = (track.boundingBox.top * scaleY) - 10f

            if (textY > 40f) {
                val textW = textPaint.measureText(label)
                val bgRect = RectF(textX - 4f, textY - 32f, textX + textW + 8f, textY + 8f)
                canvas.drawRoundRect(bgRect, 6f, 6f, textBgPaint)
                canvas.drawText(label, textX, textY, textPaint)
            }
        }
    }
}
