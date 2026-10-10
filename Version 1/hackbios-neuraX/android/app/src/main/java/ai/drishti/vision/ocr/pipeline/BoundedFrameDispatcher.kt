package ai.drishti.vision.ocr.pipeline

import android.util.Log
import ai.drishti.vision.ocr.models.OcrFramePacket
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Bounded asynchronous frame dispatcher implementing a strict "latest-frame-wins" policy.
 *
 * Guarantees:
 * 1. Camera decoding thread is NEVER blocked (trySend conflation returns immediately).
 * 2. At most ONE inference job executes concurrently on Dispatchers.Default.
 * 3. Stale intermediate frames are dropped when inference latency exceeds camera frame arrival rate.
 * 4. Mode exit immediately halts processing and discards queued frames.
 */
class BoundedFrameDispatcher(
    private val scope: CoroutineScope,
    private val onProcessFrame: suspend (OcrFramePacket) -> Unit
) {

    private val tag = "BoundedFrameDispatcher"
    // Conflated channel guarantees a buffer capacity of 1 with latest-frame-wins semantics
    private val frameChannel = Channel<OcrFramePacket>(capacity = Channel.CONFLATED)
    private var workerJob: Job? = null
    var isRunning: Boolean = false
        private set

    fun start() {
        if (isRunning) return
        isRunning = true

        workerJob = scope.launch(Dispatchers.Default) {
            Log.i(tag, "BoundedFrameDispatcher worker thread started.")
            for (packet in frameChannel) {
                if (!isActive || !isRunning) break
                try {
                    onProcessFrame(packet)
                } catch (e: Exception) {
                    Log.e(tag, "Error processing frame in OCR pipeline worker", e)
                }
            }
            Log.i(tag, "BoundedFrameDispatcher worker thread terminated.")
        }
    }

    /**
     * Submits an incoming camera frame. If inference is currently busy, the previous unconsumed frame
     * is replaced by this latest frame without blocking.
     */
    fun dispatch(packet: OcrFramePacket) {
        if (!isRunning) return
        val result = frameChannel.trySend(packet)
        if (!result.isSuccess) {
            Log.d(tag, "Dropped frame at ${packet.timestampMs} (channel full/busy)")
        }
    }

    fun stop() {
        isRunning = false
        workerJob?.cancel()
        workerJob = null
        // Drain any pending frame in channel
        while (frameChannel.tryReceive().isSuccess) {
            // discarded
        }
        Log.i(tag, "BoundedFrameDispatcher stopped.")
    }
}
