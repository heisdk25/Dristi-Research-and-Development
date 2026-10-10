package ai.drishti.utils

import android.content.Context
import android.content.SharedPreferences

import android.os.Build

/**
 * Manages user preferences and system configuration.
 */
class PreferenceManager(context: Context) {

    private val prefs: SharedPreferences = context.getSharedPreferences("drishti_settings", Context.MODE_PRIVATE)

    companion object {
        private const val KEY_ESP32_IP = "pref_esp32_ip"
        private const val KEY_TOKEN_SERVER_URL = "pref_token_server_url"
        private const val KEY_LIVEKIT_SERVER_URL = "pref_livekit_server_url"
        private const val KEY_USER_NAME = "pref_user_name"
        private const val KEY_SPEECH_RATE = "pref_speech_rate"
        private const val KEY_USE_ESP32 = "pref_use_esp32"
        private const val KEY_ESP32_ROTATION = "pref_esp32_rotation"
        private const val KEY_ESP32_MIRROR = "pref_esp32_mirror"
        private const val KEY_GOOGLE_MAPS_API_KEY = "pref_google_maps_api_key"

        const val CLOUD_VULTR_URL = "http://65.20.74.192:8000"

        val isEmulator: Boolean
            get() = (Build.BRAND.startsWith("generic") && Build.DEVICE.startsWith("generic"))
                    || Build.FINGERPRINT.startsWith("generic")
                    || Build.FINGERPRINT.startsWith("unknown")
                    || Build.HARDWARE.contains("goldfish")
                    || Build.HARDWARE.contains("ranchu")
                    || Build.MODEL.contains("google_sdk")
                    || Build.MODEL.contains("Emulator")
                    || Build.MODEL.contains("Android SDK built for x86")
    }

    val defaultTokenServerUrl: String
        get() = CLOUD_VULTR_URL

    var liveKitServerUrl: String
        get() = prefs.getString(KEY_LIVEKIT_SERVER_URL, "wss://mks-g7jf2zqv.livekit.cloud") ?: "wss://mks-g7jf2zqv.livekit.cloud"
        set(value) = prefs.edit().putString(KEY_LIVEKIT_SERVER_URL, value.trim()).apply()

    var esp32IpAddress: String
        get() = prefs.getString(KEY_ESP32_IP, "10.131.108.8") ?: "10.131.108.8"
        set(value) = prefs.edit().putString(KEY_ESP32_IP, value.trim()).apply()

    var esp32RotationDegrees: Int
        get() = prefs.getInt(KEY_ESP32_ROTATION, 90) // Default 90 degrees clockwise rotation
        set(value) = prefs.edit().putInt(KEY_ESP32_ROTATION, value).apply()

    var esp32Mirror: Boolean
        get() = prefs.getBoolean(KEY_ESP32_MIRROR, false) // Default mirror disabled (forward-facing camera)
        set(value) = prefs.edit().putBoolean(KEY_ESP32_MIRROR, value).apply()

    var tokenServerUrl: String
        get() {
            val saved = prefs.getString(KEY_TOKEN_SERVER_URL, null)
            // Automatically upgrade legacy local IP settings to the deployed 24/7 Vultr cloud URL
            if (saved == null || saved.contains("10.0.2.2") || saved.contains("127.0.0.1") || saved.contains("10.113.162") || saved.contains("10.121.179") || saved.contains("10.131.108")) {
                return CLOUD_VULTR_URL
            }
            return saved.ifEmpty { CLOUD_VULTR_URL }
        }
        set(value) = prefs.edit().putString(KEY_TOKEN_SERVER_URL, value.trim()).apply()

    var userName: String
        get() = prefs.getString(KEY_USER_NAME, "Drishti User") ?: "Drishti User"
        set(value) = prefs.edit().putString(KEY_USER_NAME, value.trim()).apply()

    var speechRate: Float
        get() = prefs.getFloat(KEY_SPEECH_RATE, 1.0f)
        set(value) = prefs.edit().putFloat(KEY_SPEECH_RATE, value).apply()

    var useEsp32Camera: Boolean
        get() = prefs.getBoolean(KEY_USE_ESP32, false) // Default to phone camera for instant out-of-the-box reliability
        set(value) = prefs.edit().putBoolean(KEY_USE_ESP32, value).apply()

    var googleMapsApiKey: String
        get() {
            val key = prefs.getString(KEY_GOOGLE_MAPS_API_KEY, null)
            return if (!key.isNullOrBlank()) key else ai.drishti.BuildConfig.MAPS_API_KEY
        }
        set(value) = prefs.edit().putString(KEY_GOOGLE_MAPS_API_KEY, value.trim()).apply()
}
