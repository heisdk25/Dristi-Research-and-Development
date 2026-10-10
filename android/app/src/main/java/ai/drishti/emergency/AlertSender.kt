package ai.drishti.emergency

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.telephony.SmsManager
import android.util.Log

data class EmergencyPayload(
    val userName: String,
    val latitude: Double,
    val longitude: Double,
    val triggerReason: String,
    val timestamp: String
)

/**
 * Dispatches multi-channel emergency notifications:
 * 1. Immediate background SMS with Google Maps coordinates.
 * 2. Targeted WhatsApp intent to primary contact.
 * 3. Direct phone dialer to primary contact (+916268110482).
 */
class AlertSender(private val context: Context) {

    private val tag = "AlertSender"

    fun sendEmergencyAlert(contacts: List<EmergencyContact>, payload: EmergencyPayload): Boolean {
        val targetContacts = if (contacts.isEmpty()) {
            listOf(EmergencyContact("Primary Caregiver", "+916268110482", "Guardian"))
        } else {
            contacts
        }

        val mapsUrl = "https://maps.google.com/?q=${payload.latitude},${payload.longitude}"
        val message = "EMERGENCY ALERT: ${payload.userName} triggered Drishti emergency (${payload.triggerReason}). " +
                "Location: $mapsUrl at ${payload.timestamp}"

        var anySent = false

        // 1. Send SMS to all contacts (headless background delivery)
        for (contact in targetContacts) {
            val sent = sendSms(contact.phoneNumber, message)
            if (sent) anySent = true
        }

        val primaryPhone = targetContacts.first().phoneNumber

        // 2. Launch WhatsApp Intent to primary contact with prefilled location
        sendWhatsApp(primaryPhone, message)

        // 3. Initiate phone call to primary contact (delayed 2.5s to allow WhatsApp activity to attach)
        try {
            Handler(Looper.getMainLooper()).postDelayed({
                dialEmergencyContact(primaryPhone)
            }, 2500L)
        } catch (e: Exception) {
            dialEmergencyContact(primaryPhone)
        }

        return anySent
    }

    private fun sendSms(phoneNumber: String, text: String): Boolean {
        return try {
            val smsManager = SmsManager.getDefault()
            val parts = smsManager.divideMessage(text)
            smsManager.sendMultipartTextMessage(phoneNumber, null, parts, null, null)
            Log.i(tag, "Emergency SMS dispatched to $phoneNumber")
            true
        } catch (e: Exception) {
            Log.e(tag, "Failed to send SMS to $phoneNumber", e)
            false
        }
    }

    private fun sendWhatsApp(phoneNumber: String, text: String) {
        val formattedNumber = phoneNumber.replace("+", "").replace(" ", "").replace("-", "")
        val url = "https://api.whatsapp.com/send?phone=$formattedNumber&text=${Uri.encode(text)}"
        try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                setPackage("com.whatsapp")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            Log.i(tag, "Dispatched WhatsApp alert intent directly to com.whatsapp for $formattedNumber")
        } catch (e: Exception) {
            Log.w(tag, "com.whatsapp not available or direct intent failed; trying standard browser intent", e)
            try {
                val fallbackIntent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(fallbackIntent)
            } catch (ex: Exception) {
                Log.e(tag, "Failed to dispatch WhatsApp intent", ex)
            }
        }
    }

    private fun dialEmergencyContact(phoneNumber: String) {
        try {
            val dialIntent = Intent(Intent.ACTION_CALL).apply {
                data = Uri.parse("tel:$phoneNumber")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(dialIntent)
            Log.i(tag, "Dispatched emergency phone call to $phoneNumber")
        } catch (e: SecurityException) {
            Log.w(tag, "CALL_PHONE permission not granted, falling back to ACTION_DIAL", e)
            try {
                val fallbackIntent = Intent(Intent.ACTION_DIAL).apply {
                    data = Uri.parse("tel:$phoneNumber")
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(fallbackIntent)
            } catch (ex: Exception) {
                Log.e(tag, "Failed to launch phone dialer fallback", ex)
            }
        } catch (e: Exception) {
            Log.e(tag, "Failed to trigger phone call", e)
        }
    }
}
