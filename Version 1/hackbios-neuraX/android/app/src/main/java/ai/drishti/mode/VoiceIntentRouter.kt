package ai.drishti.mode

import java.util.Locale

/**
 * Result of parsing a user voice utterance.
 */
sealed class VoiceAction {
    data class SwitchMode(val targetMode: DrishtiMode) : VoiceAction()
    data class EmergencyTrigger(val reason: String) : VoiceAction()
    data object EmergencyCancel : VoiceAction()
    data object QueryActiveMode : VoiceAction()
    data object QueryLocation : VoiceAction()
    data object WalkNextStep : VoiceAction()
    data object StopNavigation : VoiceAction()
    data class NavigateToDestination(val destination: String) : VoiceAction()
    data class OcrAction(val subAction: String) : VoiceAction() // "read", "summarize", "repeat"
    data class GeneralConversation(val text: String) : VoiceAction()
}

/**
 * Parses user voice transcriptions into categorized VoiceAction intents.
 * Isolated pure logic: testable in JVM unit tests without Android runtime dependencies.
 */
object VoiceIntentRouter {

    fun parse(rawUtterance: String, currentMode: DrishtiMode): VoiceAction {
        val text = rawUtterance.trim().lowercase(Locale.ROOT)

        // 1. Reserved Commands: Emergency Cancel
        if (text == "cancel" || text == "stop emergency" || text == "cancel emergency" ||
            text == "stop" || text == "i am fine" || text == "i'm fine" ||
            text == "abort" || text.contains("theek hu") || text.contains("rok do") || text.contains("band karo emergency")) {
            return VoiceAction.EmergencyCancel
        }

        // 2. Reserved Commands: Emergency Trigger
        val isEmergencyTrigger = text.contains("emergency") ||
                text.contains("save me") ||
                text.contains("mayday") ||
                text.contains("sos") ||
                text.contains("pls help") ||
                text.contains("please help") ||
                text.contains("help me") ||
                text.contains("help emergency") ||
                text.contains("bachao") ||
                text.contains("madad") ||
                text.contains("khatra")

        if (isEmergencyTrigger) {
            return VoiceAction.EmergencyTrigger(reason = "voice_phrase")
        }

        // 3. Reserved Commands: Query Active Mode
        if (text.contains("which mode") || text.contains("what mode")) {
            return VoiceAction.QueryActiveMode
        }

        // 3.1 Location Awareness & Step Control (from PR #1)
        if (text.contains("where am i") || text.contains("what place is this") || text.contains("locate me") || text.contains("kahan hu")) {
            return VoiceAction.QueryLocation
        }
        if (text.contains("stop navigation") || text.contains("cancel navigation") || text.contains("cancel route")) {
            return VoiceAction.StopNavigation
        }
        if (text == "walk" || text == "next step" || text == "next" || text == "continue" || text.contains("aage badho")) {
            return VoiceAction.WalkNextStep
        }

        // 4. Reserved Commands: Explicit Mode Switching
        if (text.contains("switch to navigation") || text.contains("go to navigation") || text.contains("navigation mode")) {
            return VoiceAction.SwitchMode(DrishtiMode.Navigation())
        }
        if (text.contains("switch to read") || text.contains("switch to reading") || text.contains("switch to ocr") || text.contains("read mode")) {
            return VoiceAction.SwitchMode(DrishtiMode.Ocr())
        }
        if (text.contains("switch to assistant") || text.contains("switch to home") || text.contains("assistant mode")) {
            return VoiceAction.SwitchMode(DrishtiMode.Assistant)
        }

        // 5. Mode-Specific Intents
        val navMatch = Regex("(?:take me to|navigate to|directions to|route to)\\s+(.+)").find(text)
        if (navMatch != null) {
            val destination = navMatch.groupValues[1].trim()
                .split(" ").joinToString(" ") { it.replaceFirstChar { c -> c.uppercase() } }
            return VoiceAction.NavigateToDestination(destination)
        }

        if (text.contains("read this") || text.contains("what does this say") || text.contains("read text")) {
            return VoiceAction.OcrAction("read")
        }
        if (text.contains("summarize this") || text.contains("summarize")) {
            return VoiceAction.OcrAction("summarize")
        }
        if (text.contains("read again") || text.contains("read slower")) {
            return VoiceAction.OcrAction("repeat")
        }

        // 6. Default Fallback: General Conversational Query
        return VoiceAction.GeneralConversation(rawUtterance)
    }
}
