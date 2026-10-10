package ai.drishti.camera

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.util.concurrent.TimeUnit
import java.net.NetworkInterface
import java.net.Inet4Address

/**
 * Connects to the ESP32-CAM HTTP MJPEG stream at http://<ip>/stream.
 * Uses a conflated frame pipeline to drop stale frames and eliminate network lag.
 * Applies hardware-accelerated Matrix transformation (90° rotation and mirroring).
 */
class Esp32StreamClient(
    private val scope: CoroutineScope,
    var rotationDegrees: Int = 90,
    var isMirrored: Boolean = false,
    private val onFrameReceived: (Bitmap) -> Unit,
    private val onStreamError: (Throwable) -> Unit
) {

    private val tag = "Esp32StreamClient"
    private var streamJob: Job? = null
    private var decoderJob: Job? = null
    private var frameChannel: Channel<ByteArray>? = null

    var isStreaming: Boolean = false
        private set

    private val client = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    fun updateOrientation(rotation: Int, mirror: Boolean) {
        this.rotationDegrees = rotation
        this.isMirrored = mirror
        Log.i(tag, "Updated ESP32 orientation: rotation=$rotation°, mirror=$mirror")
    }

    fun startStream(esp32Ip: String) {
        stopStream()
        isStreaming = true

        val channel = Channel<ByteArray>(capacity = Channel.CONFLATED)
        frameChannel = channel

        // Dedicated frame decoding worker: continuously grabs the latest available frame
        decoderJob = scope.launch(Dispatchers.Default) {
            for (jpegBytes in channel) {
                if (!isActive || !isStreaming) break
                try {
                    val rawBitmap = BitmapFactory.decodeByteArray(jpegBytes, 0, jpegBytes.size) ?: continue

                    val finalBitmap = if (rotationDegrees != 0 || isMirrored) {
                        val matrix = Matrix()
                        if (rotationDegrees != 0) {
                            matrix.postRotate(rotationDegrees.toFloat())
                        }
                        if (isMirrored) {
                            matrix.postScale(-1f, 1f)
                        }
                        Bitmap.createBitmap(rawBitmap, 0, 0, rawBitmap.width, rawBitmap.height, matrix, true)
                    } else {
                        rawBitmap
                    }

                    onFrameReceived(finalBitmap)
                } catch (e: Exception) {
                    Log.e(tag, "Error decoding frame", e)
                }
            }
        }

        streamJob = scope.launch(Dispatchers.IO) {
            var cleaned = esp32Ip.trim().removeSuffix("/")
            
            // Try auto-discovery if default/provided IP is unreachable
            try {
                val checkUrl = if (cleaned.startsWith("http")) "$cleaned/status" else "http://$cleaned/status"
                val req = Request.Builder().url(checkUrl).build()
                val checkClient = OkHttpClient.Builder().connectTimeout(1, TimeUnit.SECONDS).build()
                val res = checkClient.newCall(req).execute()
                if (!res.isSuccessful) throw Exception("Unreachable")
            } catch (e: Exception) {
                Log.w(tag, "IP $cleaned unreachable. Scanning subnet automatically...")
                val discovered = autoDiscoverEsp32Ip()
                if (discovered != null) {
                    cleaned = discovered
                }
            }

            val url = when {
                cleaned.endsWith("/stream") -> if (cleaned.startsWith("http://") || cleaned.startsWith("https://")) cleaned else "http://$cleaned"
                cleaned.startsWith("http://") || cleaned.startsWith("https://") -> "$cleaned/stream"
                else -> "http://$cleaned/stream"
            }
            Log.i(tag, "Connecting to ESP32 MJPEG stream at $url")

            while (isActive && isStreaming) {
                try {
                    val request = Request.Builder().url(url).build()
                    val response = client.newCall(request).execute()

                    if (!response.isSuccessful) {
                        throw IllegalStateException("Stream request failed with HTTP ${response.code}")
                    }

                    val inputStream = response.body?.byteStream()
                        ?: throw IllegalStateException("Empty response body from ESP32")

                    readMjpegStream(inputStream, channel)
                } catch (e: Exception) {
                    if (isActive && isStreaming) {
                        Log.w(tag, "ESP32 stream disconnected: ${e.message}. Retrying in 2 seconds...")
                        withContext(Dispatchers.Main) {
                            onStreamError(e)
                        }
                        delay(2000L)
                    }
                }
            }
        }
    }

    private fun readMjpegStream(stream: InputStream, channel: Channel<ByteArray>) {
        val buffer = ByteArray(16384)
        val frameBuffer = ByteArrayOutputStream(65536)
        var prevByte = 0

        while (isStreaming) {
            val bytesRead = stream.read(buffer)
            if (bytesRead == -1) break

            for (i in 0 until bytesRead) {
                val b = buffer[i].toInt() and 0xFF

                // Check for JPEG Start of Image (SOI): 0xFF 0xD8
                if (prevByte == 0xFF && b == 0xD8) {
                    frameBuffer.reset()
                    frameBuffer.write(0xFF)
                    frameBuffer.write(0xD8)
                } else if (prevByte == 0xFF && b == 0xD9) { // End of Image (EOI): 0xFF 0xD9
                    frameBuffer.write(b)
                    val jpegBytes = frameBuffer.toByteArray()
                    // trySend with CONFLATED channel automatically discards unread older frames,
                    // keeping the video feed perfectly in sync with zero latency lag!
                    channel.trySend(jpegBytes)
                    frameBuffer.reset()
                } else {
                    frameBuffer.write(b)
                }
                prevByte = b
            }
        }
    }

    fun stopStream() {
        isStreaming = false
        streamJob?.cancel()
        streamJob = null
        decoderJob?.cancel()
        decoderJob = null
        frameChannel?.close()
        frameChannel = null
        Log.i(tag, "ESP32 MJPEG stream stopped.")
    }

    private suspend fun autoDiscoverEsp32Ip(): String? = withContext(Dispatchers.IO) {
        try {
            var localIp: String? = null
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val iface = interfaces.nextElement()
                if (iface.isLoopback || !iface.isUp) continue
                val addresses = iface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val addr = addresses.nextElement()
                    if (addr is Inet4Address) {
                        localIp = addr.hostAddress
                        break
                    }
                }
                if (localIp != null) break
            }

            if (localIp != null && localIp.contains(".")) {
                val prefix = localIp.substringBeforeLast(".")
                val deferreds = (1..254).map { i ->
                    async {
                        val testIp = "$prefix.$i"
                        if (testIp == localIp) return@async null
                        try {
                            val request = Request.Builder().url("http://$testIp/status").build()
                            val scanClient = OkHttpClient.Builder()
                                .connectTimeout(800, TimeUnit.MILLISECONDS)
                                .readTimeout(800, TimeUnit.MILLISECONDS)
                                .build()
                            val response = scanClient.newCall(request).execute()
                            if (response.isSuccessful && response.body?.string()?.contains("\"status\":\"online\"") == true) {
                                return@async testIp
                            }
                        } catch (e: Exception) {}
                        null
                    }
                }
                val foundIp = deferreds.awaitAll().firstOrNull { it != null }
                if (foundIp != null) {
                    Log.i(tag, "Auto-discovered ESP32 at $foundIp")
                    return@withContext foundIp
                }
            }
        } catch (e: Exception) {
            Log.e(tag, "Auto-discovery failed", e)
        }
        null
    }
}
