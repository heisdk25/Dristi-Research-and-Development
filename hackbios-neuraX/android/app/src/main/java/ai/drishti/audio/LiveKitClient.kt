package ai.drishti.audio

import android.bluetooth.BluetoothHeadset
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Build
import android.util.Base64
import android.util.Log
import io.livekit.android.LiveKit
import io.livekit.android.RoomOptions
import io.livekit.android.events.RoomEvent
import io.livekit.android.room.Room
import io.livekit.android.room.track.LocalAudioTrack
import io.livekit.android.room.track.LocalVideoTrack
import io.livekit.android.room.participant.LocalParticipant
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * Manages WebRTC connectivity with LiveKit Cloud for bi-directional audio,
 * video streaming, and data channel communication with the AI Agent.
 */
class LiveKitClient(
    private val context: Context,
    private val scope: CoroutineScope,
    private val onDataReceived: (String) -> Unit,
    private val onConnectionChanged: (Boolean) -> Unit
) {

    private val tag = "LiveKitClient"
    private var room: Room? = null
    private var localAudioTrack: LocalAudioTrack? = null
    private val httpClient = OkHttpClient()

    var isConnected: Boolean = false
        private set

    // ─── Audio level monitoring ───────────────────────────────────────
    private val _inputAudioLevel = MutableStateFlow(0f)
    private val _outputAudioLevel = MutableStateFlow(0f)

    /** Microphone input level [0..1], updated in real-time by LiveKit SDK. */
    val inputAudioLevel: StateFlow<Float> = _inputAudioLevel.asStateFlow()

    /** Agent/remote audio output level [0..1]. */
    val outputAudioLevel: StateFlow<Float> = _outputAudioLevel.asStateFlow()

    private var audioMonitorJob: Job? = null
    private var isAudioRoutingRegistered = false
    private var audioDeviceCallback: AudioDeviceCallback? = null
    private var audioBroadcastReceiver: BroadcastReceiver? = null

    /**
     * Connects to LiveKit room by obtaining a token from token server.
     */
    fun connect(
        serverUrl: String,
        tokenServerBaseUrl: String,
        roomName: String,
        userName: String,
        onResolvedTokenServerUrl: ((String) -> Unit)? = null
    ) {
        scope.launch(Dispatchers.IO) {
            try {
                Log.i(tag, "Fetching LiveKit JWT token (base: $tokenServerBaseUrl, room: $roomName, user: $userName)")
                val tokenResult = fetchToken(tokenServerBaseUrl, roomName, userName)
                if (tokenResult == null) {
                    Log.e(tag, "Failed to retrieve LiveKit token from any candidate server. Running in offline fallback.")
                    onConnectionChanged(false)
                    return@launch
                }
                val (token, workingUrl) = tokenResult
                onResolvedTokenServerUrl?.invoke(workingUrl)

                val activeRoom = LiveKit.create(
                    appContext = context.applicationContext,
                    options = RoomOptions(adaptiveStream = true, dynacast = true)
                )
                room = activeRoom

                // Subscribe to room events from SharedFlow
                scope.launch {
                    activeRoom.events.events.collect { event ->
                        when (event) {
                            is RoomEvent.Connected -> {
                                Log.i(tag, "Successfully connected to LiveKit room: ${activeRoom.name}")
                                isConnected = true
                                onConnectionChanged(true)
                                registerAudioMonitoring()
                                updateAudioRouting()
                                scope.launch { publishMicrophone() }

                                // ── Start high-frequency audio level monitoring ──
                                audioMonitorJob?.cancel()
                                audioMonitorJob = scope.launch(Dispatchers.Default) {
                                    while (isConnected && room != null) {
                                        try {
                                            val currentRoom = room ?: break
                                            val localP = currentRoom.localParticipant
                                            val micRaw = localP.audioLevel
                                            val micLevel = if (micRaw > 0.001f) micRaw else (if (localP.isSpeaking) 0.35f else 0f)
                                            _inputAudioLevel.value = micLevel.coerceIn(0f, 1f)

                                            val remoteMax = currentRoom.remoteParticipants.values
                                                .maxOfOrNull { it.audioLevel } ?: 0f
                                            val anyRemoteSpeaking = currentRoom.remoteParticipants.values.any { it.isSpeaking }
                                            val agentLevel = if (remoteMax > 0.001f) remoteMax else (if (anyRemoteSpeaking) 0.45f else 0f)
                                            _outputAudioLevel.value = agentLevel.coerceIn(0f, 1f)
                                        } catch (_: Exception) {
                                            // Handle transient sync during disconnect
                                        }
                                        delay(50L)
                                    }
                                }
                            }
                            is RoomEvent.ActiveSpeakersChanged -> {
                                var localLvl = 0f
                                var remoteLvl = 0f
                                for (speaker in event.speakers) {
                                    val lvl = speaker.audioLevel
                                    if (speaker is LocalParticipant) {
                                        if (lvl > localLvl) localLvl = lvl
                                    } else {
                                        if (lvl > remoteLvl) remoteLvl = lvl
                                    }
                                }
                                if (localLvl > 0f) _inputAudioLevel.value = localLvl.coerceIn(0f, 1f)
                                if (remoteLvl > 0f) _outputAudioLevel.value = remoteLvl.coerceIn(0f, 1f)
                            }
                            is RoomEvent.Disconnected -> {
                                Log.w(tag, "Disconnected from LiveKit room")
                                isConnected = false
                                audioMonitorJob?.cancel()
                                audioMonitorJob = null
                                unregisterAudioMonitoring()
                                _inputAudioLevel.value = 0f
                                _outputAudioLevel.value = 0f
                                onConnectionChanged(false)
                            }
                            is RoomEvent.DataReceived -> {
                                val message = String(event.data)
                                Log.d(tag, "Received data packet from agent: $message")
                                onDataReceived(message)
                            }
                            is RoomEvent.TrackSubscribed -> {
                                Log.i(tag, "Subscribed to remote track: ${event.track.sid} (${event.track.kind}) from ${event.participant.identity?.value ?: event.participant.name}")
                                updateAudioRouting()
                            }
                            is RoomEvent.ParticipantConnected -> {
                                Log.i(tag, "Participant joined room: ${event.participant.identity?.value ?: event.participant.name}")
                            }
                            is RoomEvent.ParticipantDisconnected -> {
                                Log.i(tag, "Participant left room: ${event.participant.identity?.value ?: event.participant.name}")
                                _outputAudioLevel.value = 0f
                            }
                            else -> Unit
                        }
                    }
                }

                activeRoom.connect(serverUrl, token)
            } catch (e: Exception) {
                Log.e(tag, "LiveKit room connection failed", e)
                isConnected = false
                onConnectionChanged(false)
            }
        }
    }

    /**
     * Intelligently routes audio output.
     * If earbuds or headphones (Bluetooth or wired/USB) are connected, audio routes to the earbuds.
     * If no headset/earbuds are connected, audio falls back to the phone's built-in speaker.
     */
    fun updateAudioRouting() {
        try {
            val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager ?: return
            audioManager.mode = AudioManager.MODE_IN_COMMUNICATION

            val allOutputDevices = audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)

            // Check if any earbud, headphone, or headset is connected to the device
            val isHeadsetConnected = allOutputDevices.any { device ->
                device.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO ||
                device.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP ||
                device.type == AudioDeviceInfo.TYPE_BLE_HEADSET ||
                device.type == AudioDeviceInfo.TYPE_BLE_SPEAKER ||
                device.type == AudioDeviceInfo.TYPE_WIRED_HEADSET ||
                device.type == AudioDeviceInfo.TYPE_WIRED_HEADPHONES ||
                device.type == AudioDeviceInfo.TYPE_USB_HEADSET ||
                device.type == AudioDeviceInfo.TYPE_USB_DEVICE ||
                device.type == AudioDeviceInfo.TYPE_HEARING_AID
            } || (Build.VERSION.SDK_INT < Build.VERSION_CODES.S && audioManager.isWiredHeadsetOn)

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                if (isHeadsetConnected) {
                    val commHeadset = audioManager.availableCommunicationDevices.firstOrNull { device ->
                        device.type == AudioDeviceInfo.TYPE_BLE_HEADSET ||
                        device.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO ||
                        device.type == AudioDeviceInfo.TYPE_WIRED_HEADSET ||
                        device.type == AudioDeviceInfo.TYPE_WIRED_HEADPHONES ||
                        device.type == AudioDeviceInfo.TYPE_USB_HEADSET ||
                        device.type == AudioDeviceInfo.TYPE_HEARING_AID ||
                        device.type == AudioDeviceInfo.TYPE_BLE_SPEAKER
                    }

                    if (commHeadset != null) {
                        audioManager.setCommunicationDevice(commHeadset)
                        @Suppress("DEPRECATION")
                        audioManager.isSpeakerphoneOn = false
                        Log.i(tag, "Audio routed to communication headset: ${commHeadset.productName} (type ${commHeadset.type})")
                    } else {
                        // Earbud connected via A2DP/USB: clear override to let Android naturally stream to connected earbuds
                        audioManager.clearCommunicationDevice()
                        @Suppress("DEPRECATION")
                        audioManager.isSpeakerphoneOn = false
                        try {
                            audioManager.startBluetoothSco()
                            audioManager.isBluetoothScoOn = true
                        } catch (e: Exception) {
                            Log.d(tag, "Bluetooth SCO start ignored: ${e.message}")
                        }
                        Log.i(tag, "Earphone/earbud detected. Cleared communication device override to stream to earbuds.")
                    }
                } else {
                    // No headset connected - fallback to built-in speakerphone for hands-free blind assistance
                    @Suppress("DEPRECATION")
                    audioManager.stopBluetoothSco()
                    @Suppress("DEPRECATION")
                    audioManager.isBluetoothScoOn = false

                    val speakerDevice = audioManager.availableCommunicationDevices.firstOrNull {
                        it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER
                    }
                    if (speakerDevice != null) {
                        audioManager.setCommunicationDevice(speakerDevice)
                        @Suppress("DEPRECATION")
                        audioManager.isSpeakerphoneOn = true
                        Log.i(tag, "No headset detected. Audio routed to built-in speaker: ${speakerDevice.productName}")
                    } else {
                        @Suppress("DEPRECATION")
                        audioManager.isSpeakerphoneOn = true
                        Log.i(tag, "No headset detected. Speakerphone turned ON.")
                    }
                }
            } else {
                // Android 11 and below
                if (isHeadsetConnected) {
                    @Suppress("DEPRECATION")
                    audioManager.isSpeakerphoneOn = false
                    try {
                        audioManager.startBluetoothSco()
                        audioManager.isBluetoothScoOn = true
                    } catch (_: Exception) {}
                    Log.i(tag, "Headphone/earbud detected on Android < 12. Speakerphone turned OFF; audio routed to earbud.")
                } else {
                    @Suppress("DEPRECATION")
                    audioManager.stopBluetoothSco()
                    @Suppress("DEPRECATION")
                    audioManager.isBluetoothScoOn = false
                    @Suppress("DEPRECATION")
                    audioManager.isSpeakerphoneOn = true
                    Log.i(tag, "No headset detected on Android < 12. Speakerphone turned ON.")
                }
            }

            // Ensure voice call and music stream volumes are at high level
            val maxVoiceVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_VOICE_CALL)
            audioManager.setStreamVolume(AudioManager.STREAM_VOICE_CALL, (maxVoiceVol * 0.9).toInt(), 0)
            val maxMusicVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, (maxMusicVol * 0.9).toInt(), 0)
        } catch (e: Exception) {
            Log.w(tag, "Failed to update audio routing: ${e.message}")
        }
    }

    private fun registerAudioMonitoring() {
        if (isAudioRoutingRegistered) return
        try {
            val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager ?: return

            val callback = object : AudioDeviceCallback() {
                override fun onAudioDevicesAdded(addedDevices: Array<out AudioDeviceInfo>?) {
                    Log.i(tag, "Audio devices added (plugged/connected), updating routing")
                    updateAudioRouting()
                }

                override fun onAudioDevicesRemoved(removedDevices: Array<out AudioDeviceInfo>?) {
                    Log.i(tag, "Audio devices removed (unplugged/disconnected), updating routing")
                    updateAudioRouting()
                }
            }
            audioManager.registerAudioDeviceCallback(callback, null)
            audioDeviceCallback = callback

            val receiver = object : BroadcastReceiver() {
                override fun onReceive(context: Context?, intent: Intent?) {
                    val action = intent?.action ?: return
                    Log.i(tag, "Audio state broadcast received ($action), updating routing")
                    updateAudioRouting()
                }
            }
            val filter = IntentFilter().apply {
                addAction(Intent.ACTION_HEADSET_PLUG)
                addAction(BluetoothHeadset.ACTION_CONNECTION_STATE_CHANGED)
                addAction(AudioManager.ACTION_SCO_AUDIO_STATE_UPDATED)
            }
            context.registerReceiver(receiver, filter)
            audioBroadcastReceiver = receiver

            isAudioRoutingRegistered = true
            Log.i(tag, "Dynamic audio routing listeners registered.")
        } catch (e: Exception) {
            Log.w(tag, "Failed to register audio device monitoring: ${e.message}")
        }
    }

    private fun unregisterAudioMonitoring() {
        if (!isAudioRoutingRegistered) return
        try {
            val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
            audioDeviceCallback?.let {
                audioManager?.unregisterAudioDeviceCallback(it)
            }
            audioDeviceCallback = null

            audioBroadcastReceiver?.let {
                try {
                    context.unregisterReceiver(it)
                } catch (_: Exception) {}
            }
            audioBroadcastReceiver = null

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                audioManager?.clearCommunicationDevice()
            }
            @Suppress("DEPRECATION")
            audioManager?.stopBluetoothSco()
            @Suppress("DEPRECATION")
            audioManager?.isBluetoothScoOn = false
            @Suppress("DEPRECATION")
            audioManager?.isSpeakerphoneOn = false
            audioManager?.mode = AudioManager.MODE_NORMAL

            isAudioRoutingRegistered = false
            Log.i(tag, "Dynamic audio routing listeners unregistered and audio mode restored.")
        } catch (e: Exception) {
            Log.w(tag, "Failed to unregister audio device monitoring: ${e.message}")
        }
    }

    private suspend fun publishMicrophone() {
        val activeRoom = room ?: return
        try {
            activeRoom.localParticipant.setMicrophoneEnabled(true)
            Log.i(tag, "Microphone enabled and audio track published to room.")
        } catch (e: Exception) {
            Log.e(tag, "Failed to enable microphone", e)
        }
    }

    fun publishVideoTrack(videoTrack: LocalVideoTrack) {
        val activeRoom = room ?: return
        scope.launch {
            try {
                activeRoom.localParticipant.publishVideoTrack(videoTrack)
                Log.i(tag, "Published video track to room.")
            } catch (e: Exception) {
                Log.e(tag, "Failed to publish video track", e)
            }
        }
    }

    fun sendData(jsonString: String) {
        val activeRoom = room ?: return
        scope.launch(Dispatchers.IO) {
            try {
                activeRoom.localParticipant.publishData(jsonString.toByteArray())
                if (jsonString.length > 200) {
                    Log.d(tag, "Sent data packet to agent (${jsonString.length} bytes)")
                } else {
                    Log.d(tag, "Sent data packet to agent: $jsonString")
                }
            } catch (e: Exception) {
                Log.e(tag, "Failed to send data channel message", e)
            }
        }
    }

    fun disconnect() {
        audioMonitorJob?.cancel()
        audioMonitorJob = null
        unregisterAudioMonitoring()
        _inputAudioLevel.value = 0f
        _outputAudioLevel.value = 0f
        try {
            room?.disconnect()
            room?.release()
        } catch (e: Exception) {
            Log.w(tag, "Error disconnecting room", e)
        }
        try {
            localAudioTrack?.stop()
            localAudioTrack?.dispose()
        } catch (e: Exception) {
            Log.w(tag, "Error disposing audio track", e)
        }
        localAudioTrack = null
        room = null
        isConnected = false
        onConnectionChanged(false)
        Log.i(tag, "LiveKit room disconnected and cleaned up.")
    }

    private fun generateLocalToken(roomName: String, userName: String): String {
        val apiKey = "APIP9k9XrcGvovw"
        val apiSecret = "86UkWnwzmmzUSGqYubq3ID1vCTpSVANBkooQ83NEaYG"

        fun base64Url(bytes: ByteArray): String {
            return Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
        }

        val now = System.currentTimeMillis() / 1000
        val headerJson = JSONObject().apply {
            put("alg", "HS256")
            put("typ", "JWT")
        }.toString()

        val videoGrants = JSONObject().apply {
            put("room", roomName)
            put("roomJoin", true)
            put("canPublish", true)
            put("canSubscribe", true)
            put("canPublishData", true)
        }

        val payloadJson = JSONObject().apply {
            put("exp", now + 86400)
            put("iss", apiKey)
            put("nbf", now - 10)
            put("sub", userName)
            put("video", videoGrants)
        }.toString()

        val headerB64 = base64Url(headerJson.toByteArray(Charsets.UTF_8))
        val payloadB64 = base64Url(payloadJson.toByteArray(Charsets.UTF_8))
        val dataToSign = "$headerB64.$payloadB64"

        val mac = Mac.getInstance("HmacSHA256")
        val secretKey = SecretKeySpec(apiSecret.toByteArray(Charsets.UTF_8), "HmacSHA256")
        mac.init(secretKey)
        val signatureBytes = mac.doFinal(dataToSign.toByteArray(Charsets.US_ASCII))
        val signatureB64 = base64Url(signatureBytes)

        return "$dataToSign.$signatureB64"
    }

    private fun fetchToken(primaryUrl: String, roomName: String, userName: String): Pair<String, String>? {
        // Smart candidates list: Try primary first, then ADB USB reverse loopback, then Wi-Fi host IP, then emulator
        val candidates = linkedSetOf(
            primaryUrl,
            "http://127.0.0.1:8000",
            "http://10.131.108.33:8000",
            "http://10.0.2.2:8000"
        )

        for (candidate in candidates) {
            val cleanBase = candidate.trim().trimEnd('/')
            if (cleanBase.isEmpty()) continue
            try {
                Log.i(tag, "Attempting token fetch from candidate: $cleanBase")
                val encodedRoom = java.net.URLEncoder.encode(roomName, "UTF-8")
                val encodedUser = java.net.URLEncoder.encode(userName, "UTF-8")
                val url = "$cleanBase/token?room=$encodedRoom&user=$encodedUser"
                val request = Request.Builder().url(url).get().build()

                val fastClient = httpClient.newBuilder()
                    .connectTimeout(java.time.Duration.ofMillis(1200))
                    .readTimeout(java.time.Duration.ofMillis(1500))
                    .build()

                fastClient.newCall(request).execute().use { response ->
                    if (response.isSuccessful) {
                        val body = response.body?.string()
                        if (body != null) {
                            val json = JSONObject(body)
                            if (json.has("token")) {
                                val token = json.getString("token")
                                Log.i(tag, "Successfully acquired LiveKit token from $cleanBase")
                                return Pair(token, cleanBase)
                            }
                        }
                    } else {
                        Log.w(tag, "Candidate $cleanBase responded with HTTP ${response.code}")
                    }
                }
            } catch (e: Exception) {
                Log.d(tag, "Candidate $cleanBase unreachable: ${e.message}")
            }
        }

        // ── Robust fallback: generate signed LiveKit JWT on-device in 1 millisecond ──
        Log.i(tag, "Remote token servers unreachable; generating authenticated LiveKit JWT on-device.")
        return try {
            val token = generateLocalToken(roomName, userName)
            Pair(token, "local://on-device")
        } catch (e: Exception) {
            Log.e(tag, "Failed to generate local token", e)
            null
        }
    }
}
