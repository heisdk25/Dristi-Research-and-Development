package ai.drishti

import ai.drishti.mode.DrishtiMode
import ai.drishti.mode.VoiceAction
import ai.drishti.mode.VoiceIntentRouter
import org.junit.Assert.*
import org.junit.Test

class VoiceIntentRouterTest {

    @Test
    fun testParseEmergencyTriggers() {
        val action = VoiceIntentRouter.parse("help emergency right now", DrishtiMode.Assistant)
        assertTrue(action is VoiceAction.EmergencyTrigger)
        assertEquals("voice_phrase", (action as VoiceAction.EmergencyTrigger).reason)

        val action2 = VoiceIntentRouter.parse("emergency pls help", DrishtiMode.Assistant)
        assertTrue(action2 is VoiceAction.EmergencyTrigger)

        val action3 = VoiceIntentRouter.parse("emergency please help", DrishtiMode.Assistant)
        assertTrue(action3 is VoiceAction.EmergencyTrigger)

        val action4 = VoiceIntentRouter.parse("pls help", DrishtiMode.Assistant)
        assertTrue(action4 is VoiceAction.EmergencyTrigger)

        val action5 = VoiceIntentRouter.parse("bachao", DrishtiMode.Assistant)
        assertTrue(action5 is VoiceAction.EmergencyTrigger)
    }

    @Test
    fun testParseEmergencyCancel() {
        val action1 = VoiceIntentRouter.parse("cancel", DrishtiMode.Emergency("test"))
        assertTrue(action1 is VoiceAction.EmergencyCancel)

        val action2 = VoiceIntentRouter.parse("stop emergency", DrishtiMode.Emergency("test"))
        assertTrue(action2 is VoiceAction.EmergencyCancel)

        val action3 = VoiceIntentRouter.parse("i am fine", DrishtiMode.Emergency("test"))
        assertTrue(action3 is VoiceAction.EmergencyCancel)
    }

    @Test
    fun testParseModeSwitches() {
        val navAction = VoiceIntentRouter.parse("switch to navigation", DrishtiMode.Assistant)
        assertTrue(navAction is VoiceAction.SwitchMode)
        assertTrue((navAction as VoiceAction.SwitchMode).targetMode is DrishtiMode.Navigation)

        val ocrAction = VoiceIntentRouter.parse("switch to read mode", DrishtiMode.Assistant)
        assertTrue(ocrAction is VoiceAction.SwitchMode)
        assertTrue((ocrAction as VoiceAction.SwitchMode).targetMode is DrishtiMode.Ocr)

        val assistantAction = VoiceIntentRouter.parse("switch to assistant", DrishtiMode.Navigation())
        assertTrue(assistantAction is VoiceAction.SwitchMode)
        assertTrue((assistantAction as VoiceAction.SwitchMode).targetMode is DrishtiMode.Assistant)
    }

    @Test
    fun testParseNavigationDestination() {
        val action = VoiceIntentRouter.parse("take me to the railway station", DrishtiMode.Navigation())
        assertTrue(action is VoiceAction.NavigateToDestination)
        assertTrue((action as VoiceAction.NavigateToDestination).destination.contains("Railway Station"))
    }

    @Test
    fun testParseOcrActions() {
        val action = VoiceIntentRouter.parse("read this label", DrishtiMode.Ocr())
        assertTrue(action is VoiceAction.OcrAction)
        assertEquals("read", (action as VoiceAction.OcrAction).subAction)

        val summaryAction = VoiceIntentRouter.parse("summarize this please", DrishtiMode.Ocr())
        assertTrue(summaryAction is VoiceAction.OcrAction)
        assertEquals("summarize", (summaryAction as VoiceAction.OcrAction).subAction)
    }

    @Test
    fun testParseLocationAndNavigationControls() {
        val locAction = VoiceIntentRouter.parse("where am i right now", DrishtiMode.Assistant)
        assertTrue(locAction is VoiceAction.QueryLocation)

        val walkAction = VoiceIntentRouter.parse("next step", DrishtiMode.Navigation())
        assertTrue(walkAction is VoiceAction.WalkNextStep)

        val stopAction = VoiceIntentRouter.parse("stop navigation", DrishtiMode.Navigation())
        assertTrue(stopAction is VoiceAction.StopNavigation)
    }

    @Test
    fun testParseGeneralConversationFallback() {
        val action = VoiceIntentRouter.parse("what time is it", DrishtiMode.Assistant)
        assertTrue(action is VoiceAction.GeneralConversation)
        assertEquals("what time is it", (action as VoiceAction.GeneralConversation).text)
    }
}
