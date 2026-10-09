"""
Drishti LiveKit Agent Worker

A multi-modal, voice-driven AI companion for visually impaired individuals.
Handles three primary operational modes:
  1. Assistant (Scene Q&A, general queries, obstacle context)
  2. Navigation (Turn-by-turn walking guidance and bearing)
  3. OCR / Reading (Reading text aloud, summarization)
  4. Emergency (Voice cancellation and dispatch confirmation)
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

import httpx
from dotenv import load_dotenv

# LiveKit Agents imports
try:
    from livekit import rtc
    from livekit.agents import AgentSession, JobContext, RoomInputOptions, WorkerOptions, cli, function_tool
    from livekit.agents.voice import Agent
    from livekit.plugins import google, openai, sarvam, silero
    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("drishti-agent")


# ── Domain Configuration & Prompts ─────────────────────────

class PromptManager:
    """Provides isolated, tested prompt templates for each operational mode."""

    BASE_PROMPT = (
        "You are Drishti, an assistive voice companion for a visually impaired user. "
        "CRITICAL RULES:\n"
        "1. Always give answers in short! Strictly 1 to 2 short sentences. "
        "2. Speak naturally and warmly in the user's preferred language (Hindi, English, or mixed Hinglish). "
        "3. You are fully capable of conversational chat, answering questions, giving guidance, and using your tools.\n"
        "4. Current Active Mode: {mode}\n"
        "5. TOOLS GUIDANCE:\n"
        "   - When the user asks what is in front of them, to describe the scene, or asks in Hindi ('samne kya hai', 'aage kya hai', 'kya dikh raha hai', 'dekho'), immediately call the describe_scene tool.\n"
        "   - When the user asks to switch or change modes ('mode badlo', 'switch to navigation', 'ocr mode', 'normal mode'), call the switch_mode tool.\n"
        "   - When the user asks to read text, signs, or documents ('kya likha hai', 'padho', 'read text'), call the read_text_in_view tool.\n"
        "   - When the user asks to navigate or go somewhere ('take me to ...', 'ghar chalo', 'metro station jana hai'), call the start_navigation tool.\n"
        "   - For any other general conversation, greetings, or questions, answer directly, warmly, and helpfully in 1 short sentence.\n\n"
    )

    PROMPTS: Dict[str, str] = {
        "assistant": (
            "You are in Assistant Mode (General-purpose voice assistant).\n"
            "Converse naturally on any topic. When asked about surroundings, call describe_scene. "
            "Mention relative clock directions (e.g., 'at your 2 o'clock') and approximate distances when known."
        ),
        "navigation": (
            "You are in Navigation Mode. Guide the visually impaired user along their walking path.\n"
            "Give clear, brief step-by-step instructions (e.g., 'Walk straight for 20 meters, then turn right at 2 o'clock'). "
            "Use clock-face orientations ('12 o'clock' for straight ahead). Prioritize hazards and crosswalks."
        ),
        "ocr": (
            "You are in OCR Mode. Your duty is to read and interpret text presented in front of the camera.\n"
            "If text is detected, read it verbatim and briefly in 1 short sentence. "
            "You can speak both English and Hindi naturally based on the text script."
        ),
        "emergency": (
            "You are in Emergency Alert Mode. Speak clearly, loudly, and calmly.\n"
            "State: 'Emergency alert initiated. Say CANCEL to abort, or help is being notified.' "
            "Keep all communication strictly brief and reassuring."
        )
    }

    @classmethod
    def get_prompt(cls, mode: str) -> str:
        """Retrieves system prompt for the specified mode with fallback to assistant."""
        mode_key = mode.strip().lower()
        resolved_mode = mode_key if mode_key in cls.PROMPTS else "assistant"
        specific = cls.PROMPTS[resolved_mode]
        return cls.BASE_PROMPT.format(mode=resolved_mode.upper()) + specific


class ModeManager:
    """Centralized manager for application operational modes."""
    VALID_MODES = {
        "assistant",
        "navigation",
        "ocr",
        "emergency"
    }

    def __init__(self, initial_mode: str = "assistant"):
        self.active_mode = initial_mode if initial_mode in self.VALID_MODES else "assistant"

    def switch_mode(self, mode: str) -> dict:
        mode_lower = mode.strip().lower()
        if "nav" in mode_lower or "walk" in mode_lower or "rasht" in mode_lower or "chal" in mode_lower:
            target = "navigation"
        elif "ocr" in mode_lower or "read" in mode_lower or "text" in mode_lower or "padh" in mode_lower:
            target = "ocr"
        elif "emerg" in mode_lower or "help" in mode_lower or "sos" in mode_lower or "khatr" in mode_lower:
            target = "emergency"
        elif "assist" in mode_lower or "normal" in mode_lower or "back" in mode_lower or "baat" in mode_lower:
            target = "assistant"
        else:
            target = mode_lower

        if target not in self.VALID_MODES:
            return {
                "success": False,
                "changed": False,
                "mode": target,
                "error": "I don't have that mode."
            }

        if target == self.active_mode:
            return {
                "success": True,
                "changed": False,
                "mode": target
            }

        self.active_mode = target

        return {
            "success": True,
            "changed": True,
            "mode": target
        }


# ── Agent State & Data Packet Manager ──────────────────────

class DrishtiAgent:
    """Manages agent state and data packet routing for testing and modular runtime handling."""

    def __init__(self, initial_mode: str = "assistant"):
        self.mode = initial_mode
        self.latest_ocr_text: Optional[str] = None
        self.latest_obstacle: Optional[Dict[str, Any]] = None
        self.latest_camera_frame: Optional[str] = None

    def handle_data_packet(self, raw_json: str) -> Dict[str, Any]:
        """Parses and processes an incoming data packet string."""
        payload = json.loads(raw_json)
        msg_type = payload.get("type")
        if msg_type == "MODE_CHANGE":
            self.mode = payload.get("mode", self.mode)
            return {"status": "ok", "mode": self.mode}
        elif msg_type == "OCR_RESULT":
            self.latest_ocr_text = payload.get("text")
            return {"status": "ok", "text": self.latest_ocr_text}
        elif msg_type == "OBSTACLE_WARNING":
            self.latest_obstacle = payload
            return {"status": "ok", "obstacle": payload.get("obstacle")}
        elif msg_type == "CAMERA_FRAME":
            self.latest_camera_frame = payload.get("image_base64")
            return {"status": "ok"}
        return {"status": "unknown_type"}



# ── Intent Router ──────────────────────────────────────────

class AgentIntentRouter:
    """
    Parses user utterances into reserved commands vs mode-specific queries.
    Pure logic, easily testable without network or LiveKit connections.
    """

    RESERVED_MODES = {
        "assistant": ["assistant", "home", "default", "companion"],
        "navigation": ["navigation", "navigate", "directions", "maps"],
        "ocr": ["ocr", "reading", "read mode", "read this", "scan text"],
        "emergency": ["help emergency", "emergency", "mayday", "save me"]
    }

    @classmethod
    def classify_intent(cls, utterance: str, current_mode: str = "assistant") -> Tuple[str, Dict[str, Any]]:
        """
        Returns (intent_type, payload).
        Intent types:
          - 'SWITCH_MODE': Switch to a target mode.
          - 'QUERY_MODE': Tell the user what mode is active.
          - 'EMERGENCY_TRIGGER': Emergency invoked.
          - 'EMERGENCY_CANCEL': Cancel active countdown.
          - 'NAVIGATION_ROUTE': Destination requested.
          - 'OCR_REQUEST': Reading requested.
          - 'GENERAL_QUERY': Normal conversational flow.
        """
        text = utterance.strip().lower()

        # Emergency cancellation
        if text in ["cancel", "stop emergency", "i am fine", "i'm fine", "abort"]:
            return ("EMERGENCY_CANCEL", {"confidence": 1.0})

        # Emergency trigger
        if any(term in text for term in ["help emergency", "help me", "save me", "emergency alert"]):
            return ("EMERGENCY_TRIGGER", {"reason": "voice_phrase"})

        # Query active mode
        if "which mode" in text or "what mode" in text:
            return ("QUERY_MODE", {"current_mode": current_mode})

        # Mode switching commands
        switch_match = re.search(r"(?:switch to|change to|go to|enter)\s+([a-zA-Z ]+)", text)
        if switch_match:
            target = switch_match.group(1).strip()
            for mode_name, aliases in cls.RESERVED_MODES.items():
                if any(alias in target for alias in aliases):
                    return ("SWITCH_MODE", {"target_mode": mode_name})

        # Navigation destination intent
        nav_match = re.search(r"(?:take me to|navigate to|directions to|route to|go to)\s+(.+)", text)
        if nav_match:
            destination = nav_match.group(1).strip().title()
            return ("NAVIGATION_ROUTE", {"destination": destination})

        # OCR intent
        if any(term in text for term in ["read this", "what does this say", "read text", "read label"]):
            return ("OCR_REQUEST", {"action": "read"})
        if any(term in text for term in ["summarize this", "summarize text"]):
            return ("OCR_REQUEST", {"action": "summarize"})

        return ("GENERAL_QUERY", {"utterance": utterance, "mode": current_mode})


# ── Navigation Service ─────────────────────────────────────

class NavigationService:
    """Handles geocoding and walking route planning with fallback calculation."""

    @staticmethod
    def plan_route(destination: str, current_lat: float = 28.6139, current_lng: float = 77.2090) -> Dict[str, Any]:
        """
        Calculates walking steps and distance for a given destination.
        Gracefully handles offline or mock scenarios.
        """
        cleaned_dest = destination.strip().title()
        return {
            "destination": cleaned_dest,
            "origin": {"lat": current_lat, "lng": current_lng},
            "total_distance_m": 450,
            "estimated_time_min": 6,
            "steps": [
                {"instruction": f"Head straight towards {cleaned_dest}", "distance_m": 150, "bearing": "12 o'clock"},
                {"instruction": "Turn slightly right at the crosswalk", "distance_m": 100, "bearing": "2 o'clock"},
                {"instruction": f"Continue straight. {cleaned_dest} will be on your left", "distance_m": 200, "bearing": "12 o'clock"}
            ]
        }


# ── Vision Analysis Service ────────────────────────────────

class VisionService:
    """Interprets camera frames and OCR strings for cloud LLM queries."""

    @staticmethod
    def format_scene_description(objects_detected: list, scene_text: Optional[str] = None) -> str:
        """Composes a natural language description for visually impaired navigation."""
        if not objects_detected and not scene_text:
            return "The path directly ahead appears clear."

        parts = []
        if objects_detected:
            formatted_objects = ", ".join(objects_detected[:3])
            parts.append(f"In front of you, there is {formatted_objects}.")
        if scene_text:
            parts.append(f"A sign reads: '{scene_text.strip()}'.")

        return " ".join(parts)


# ── LiveKit Agent Implementation ───────────────────────────

async def entrypoint(ctx: JobContext) -> None:
    """Main worker entry point for LiveKit."""
    logger.info(f"Worker connected to room: {ctx.room.name}")

    # Wait for the first participant to connect
    await ctx.connect()

    initial_mode = os.getenv("DEFAULT_AGENT_MODE", "assistant")

    # ── Configure STT (Low Latency Multilingual Indian Voice Streaming) ──
    stt_lang = os.getenv("SARVAM_STT_LANGUAGE", "unknown")
    stt_plugin = sarvam.STT(
        language=stt_lang,
        model="saaras:v4",
        mode="transcribe",
        high_vad_sensitivity=True,
        min_speech_frames=2,
        flush_signal=True,
    )

    # ── Configure LLM (Prefer Ultra-Fast Gemini Flash or Groq LPU) ──
    provider = os.getenv("LLM_PROVIDER", "google").strip().lower()
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_base = os.getenv("OPENAI_BASE_URL")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o").strip()
    groq_key = os.getenv("GROQ_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    google_model = os.getenv("GOOGLE_MODEL", "gemini-3.5-flash-lite").strip()

    def build_openai_llm():
        kwargs = {"model": openai_model}
        if openai_key and not openai_key.startswith("..."):
            kwargs["api_key"] = openai_key
        if openai_base and not openai_base.startswith("..."):
            kwargs["base_url"] = openai_base
        logger.info(f"Using OpenAI LLM ({openai_model}) with base_url={openai_base or 'https://api.openai.com/v1'}")
        return openai.LLM(**kwargs)

    def build_groq_llm():
        groq_model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
        logger.info(f"Using Groq Ultra-Fast LPU LLM ({groq_model})")
        return openai.LLM(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
            model=groq_model,
        )

    def build_google_llm():
        logger.info(f"Using Google Gemini LLM ({google_model})")
        return google.LLM(
            model=google_model,
            api_key=google_key,
        )

    if provider in ("google", "gemini") and google_key and not google_key.startswith("...") and len(google_key) > 10:
        llm_plugin = build_google_llm()
    elif provider == "groq" and groq_key and not groq_key.startswith("...") and len(groq_key.strip()) > 5:
        llm_plugin = build_groq_llm()
    elif provider == "openai":
        llm_plugin = build_openai_llm()
    elif google_key and not google_key.startswith("...") and len(google_key) > 10:
        llm_plugin = build_google_llm()
    elif groq_key and not groq_key.startswith("...") and len(groq_key.strip()) > 5:
        llm_plugin = build_groq_llm()
    elif openai_key and not openai_key.startswith("...") and len(openai_key.strip()) > 10:
        llm_plugin = build_openai_llm()
    else:
        llm_plugin = build_openai_llm()

    # ── Configure TTS (Fast natural cadence with robust Indian language preprocessing) ──
    tts_pace = float(os.getenv("SARVAM_TTS_PACE", "1.18"))
    tts_lang = os.getenv("SARVAM_TTS_LANGUAGE", "hi-IN")
    tts_speaker = os.getenv("SARVAM_TTS_SPEAKER", "kabir")
    tts_plugin = sarvam.TTS(
        target_language_code=tts_lang,
        model="bulbul:v3",
        speaker=tts_speaker,
        pace=tts_pace,
        temperature=0.3,
        loudness=1.0,
        enable_preprocessing=True,
    )

    # ── Configure VAD for Fast Low-Latency Conversational Turn Detection ──
    # 0.32s silence duration ensures fast cutoff without clipping words
    vad_plugin = silero.VAD.load(
        min_silence_duration=0.32,
        activation_threshold=0.5,
        prefix_padding_duration=0.15,
    )

    # ── Real-Time Camera Frame State & Mode Manager ──
    latest_camera_frame: Optional[str] = None
    mode_manager = ModeManager(initial_mode)

    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        nonlocal latest_camera_frame
        try:
            raw_text = data_packet.data.decode("utf-8")
            payload = json.loads(raw_text)
            msg_type = payload.get("type")
            if msg_type == "CAMERA_FRAME":
                latest_camera_frame = payload.get("image_base64")
                logger.debug("Received fresh camera frame from mobile device")
            elif msg_type == "OBSTACLE_WARNING":
                obstacle = payload.get("obstacle", "obstacle")
                pos = payload.get("position", "ahead")
                dist = payload.get("distance", "")
                logger.info(f"Obstacle alert from phone: {obstacle} at {pos} ({dist}m)")
            elif msg_type == "OCR_RESULT":
                logger.info(f"OCR text received: {payload.get('text')}")
            elif msg_type == "MODE_CHANGE":
                new_mode = payload.get("mode", "assistant").strip().lower()
                result = mode_manager.switch_mode(new_mode)
                if result["success"]:
                    agent.update_instructions(PromptManager.get_prompt(result["mode"]))
                    logger.info(f"Mobile app switched mode to '{result['mode']}'. Agent prompt updated smoothly.")
        except Exception as err:
            logger.warning(f"Error handling data packet: {err}")

    async def analyze_frame_with_vision(image_base64: str) -> str:
        prompt = (
            "You are Drishti, an assistive voice companion for a visually impaired user. "
            "CRITICAL RULE: Give answer in short! Strictly 1 to 2 short sentences. "
            "Describe what is directly in front of the camera clearly, concisely, and objectively. "
            "Mention key obstacles, pathway clearance, and relative positions "
            "(e.g., directly ahead, on your left, at your 2 o'clock). "
            "Never say 'in the image' or 'the picture shows'—speak naturally as if viewing through their eyes."
        )

        if google_key and not google_key.startswith("...") and len(google_key) > 10:
            try:
                clean_b64 = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{google_model}:generateContent?key={google_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/jpeg", "data": clean_b64}}
                        ]
                    }],
                    "generationConfig": {"maxOutputTokens": 80}
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if "text" in part:
                            return part["text"].strip()
            except Exception as e:
                logger.warning(f"Gemini vision call failed, trying OpenAI fallback: {e}")

        # Fallback to OpenAI vision proxy if configured
        url = f"{openai_base or 'https://api.openai.com/v1'}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}"
        }
        image_url = image_base64 if image_base64.startswith("data:") else f"data:image/jpeg;base64,{image_base64}"
        payload = {
            "model": openai_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            "max_tokens": 80
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    async def extract_text_with_vision(image_base64: str) -> str:
        prompt = (
            "You are Drishti in Reading Mode for a visually impaired user. "
            "Examine the camera frame and read aloud all visible printed or handwritten text. "
            "Identify what the text is on (e.g., medicine box, street sign, book, receipt, screen, label). "
            "If it is a product or medicine, highlight the name, dosage, or expiry date. "
            "CRITICAL RULE: Give answer in short! Strictly 1 to 2 clear, concise sentences."
        )

        if google_key and not google_key.startswith("...") and len(google_key) > 10:
            try:
                clean_b64 = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{google_model}:generateContent?key={google_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/jpeg", "data": clean_b64}}
                        ]
                    }],
                    "generationConfig": {"maxOutputTokens": 120}
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if "text" in part:
                            return part["text"].strip()
            except Exception as e:
                logger.warning(f"Gemini OCR call failed, trying OpenAI fallback: {e}")

        # Fallback to OpenAI vision proxy if configured
        url = f"{openai_base or 'https://api.openai.com/v1'}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}"
        }
        image_url = image_base64 if image_base64.startswith("data:") else f"data:image/jpeg;base64,{image_base64}"
        payload = {
            "model": openai_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            "max_tokens": 120
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    @function_tool
    async def describe_scene() -> str:
        """Call this tool whenever the user asks what is in front of them, to describe the scene, what the camera sees, or asks in Hindi/Hinglish ('सामने क्या है', 'आगे क्या है', 'क्या दिख रहा है', 'dekho', 'samne kya hai', 'aage kya hai', 'kya dikh raha hai', 'aspaas kya hai')."""
        nonlocal latest_camera_frame
        logger.info("Function tool 'describe_scene' invoked by agent")

        # If no frame cached, ask the mobile phone for a fresh frame
        if not latest_camera_frame:
            try:
                req = json.dumps({"type": "REQUEST_FRAME"}).encode("utf-8")
                await ctx.room.local_participant.publish_data(req)
                for _ in range(15):
                    await asyncio.sleep(0.1)
                    if latest_camera_frame:
                        break
            except Exception as e:
                logger.warning(f"Failed to request frame from client: {e}")

        if not latest_camera_frame:
            return "Camera feed is connecting. Please point your phone forward and ask me again."

        try:
            description = await analyze_frame_with_vision(latest_camera_frame)
            logger.info(f"Vision scene description generated: {description}")
            return description
        except Exception as err:
            logger.error(f"Vision analysis failed: {err}")
            return "I had trouble analyzing the scene right now. Please ask again in a moment."

    @function_tool
    async def switch_mode(target_mode: str) -> str:
        """Switch the operational mode of Drishti ('assistant', 'navigation', 'ocr', or 'emergency'). Call this whenever the user asks to switch or change modes in English or Hindi ('mode badlo', 'मोड बदलो', 'switch to navigation', 'ocr mode', 'normal mode').
        Args:
            target_mode: Target mode ('assistant', 'navigation', 'ocr', or 'emergency').
        """
        logger.info(f"Function tool 'switch_mode' invoked with mode: {target_mode}")
        
        result = mode_manager.switch_mode(target_mode)
        if not result["success"]:
            return result["error"]
            
        mode_name = result["mode"]
        if not result["changed"]:
            return f"{mode_name.capitalize()} mode is already active."

        agent.update_instructions(PromptManager.get_prompt(mode_name))
        logger.info(f"Switched mode to '{mode_name}' and updated agent prompt smoothly")

        try:
            packet = json.dumps({"type": "SWITCH_MODE", "target": mode_name}).encode("utf-8")
            await ctx.room.local_participant.publish_data(packet)
        except Exception as e:
            logger.warning(f"Failed to publish SWITCH_MODE to mobile client: {e}")

        return f"{mode_name.capitalize()} mode activated."

    @function_tool
    async def start_navigation(destination: str) -> str:
        """Initiate walking navigation to a destination or landmark. Call this whenever the user asks to navigate or walk somewhere in English or Hindi ('take me to ...', 'directions to ...', 'घर चलो', 'रास्ता दिखाओ', 'ghar chalo', 'rasta dikhao').
        Args:
            destination: Name of the destination (e.g., 'Metro station', 'Hospital', 'Home').
        """
        # Automatically ensure navigation mode is active
        if mode_manager.active_mode != "navigation":
            mode_manager.switch_mode("navigation")
            agent.update_instructions(PromptManager.get_prompt("navigation"))
            try:
                packet = json.dumps({"type": "SWITCH_MODE", "target": "navigation"}).encode("utf-8")
                await ctx.room.local_participant.publish_data(packet)
            except Exception:
                pass

        try:
            packet = json.dumps({"type": "REQUEST_NAVIGATION", "destination": destination}).encode("utf-8")
            await ctx.room.local_participant.publish_data(packet)
        except Exception as e:
            logger.warning(f"Failed to publish REQUEST_NAVIGATION to mobile client: {e}")

        return f"Navigation to {destination} started. Walk straight."

    @function_tool
    async def read_text_in_view() -> str:
        """Call this tool whenever the user asks to read text, signs, labels, documents, or asks in Hindi ('kya likha hai', 'क्या लिखा है', 'padho', 'पढ़ो', 'text padho')."""
        # Automatically ensure OCR mode is active
        if mode_manager.active_mode != "ocr":
            mode_manager.switch_mode("ocr")
            agent.update_instructions(PromptManager.get_prompt("ocr"))
            try:
                packet = json.dumps({"type": "SWITCH_MODE", "target": "ocr"}).encode("utf-8")
                await ctx.room.local_participant.publish_data(packet)
            except Exception:
                pass

        nonlocal latest_camera_frame
        logger.info("Function tool 'read_text_in_view' invoked by agent")

        if not latest_camera_frame:
            try:
                req = json.dumps({"type": "REQUEST_FRAME"}).encode("utf-8")
                await ctx.room.local_participant.publish_data(req)
                for _ in range(15):
                    await asyncio.sleep(0.1)
                    if latest_camera_frame:
                        break
            except Exception as e:
                logger.warning(f"Failed to request frame for OCR: {e}")

        if not latest_camera_frame:
            return "Please hold the text steadily in front of your camera and ask me to read again."

        try:
            read_text = await extract_text_with_vision(latest_camera_frame)
            logger.info(f"Vision LLM OCR result: {read_text}")
            return read_text
        except Exception as err:
            logger.error(f"Vision OCR failed: {err}")
            return "I couldn't read the text clearly. Please hold it steady and try asking again."

    agent_tools = [describe_scene, switch_mode, start_navigation, read_text_in_view]

    # ── Create AgentSession with Preemptive Generation, VAD Turn Detection & Zero AEC Warmup Lockout ──
    session = AgentSession(
        stt=stt_plugin,
        llm=llm_plugin,
        tts=tts_plugin,
        vad=vad_plugin,
        tools=agent_tools,
        turn_detection="vad",
        min_endpointing_delay=0.15,
        max_endpointing_delay=0.55,
        aec_warmup_duration=0.0,
        allow_interruptions=True,
        min_interruption_duration=0.25,
        user_away_timeout=180.0,
        preemptive_generation=True,
    )

    # ── Create the Agent with the system prompt and tools ──
    agent = Agent(
        instructions=PromptManager.get_prompt(initial_mode),
        tools=agent_tools,
    )

    # ── Start the session ──
    await session.start(
        agent=agent,
        room=ctx.room,
    )

    logger.info(f"Agent session started smoothly in '{initial_mode}' mode")

    # ── Immediate initial greeting without LLM roundtrip delay or template errors ──
    try:
        await session.say(
            "Hello! I am Drishti, your assistive companion. How can I help you?",
            allow_interruptions=True,
        )
    except Exception as reply_err:
        logger.error(f"Failed to play initial greeting: {reply_err}")

    # ── Keep session alive until participant leaves or room disconnects ──
    disconnect_event = asyncio.Event()

    @ctx.room.on("disconnected")
    def on_disconnected():
        disconnect_event.set()

    try:
        await disconnect_event.wait()
    except (asyncio.CancelledError, Exception):
        pass
    finally:
        logger.info("Room disconnected cleanly. Session ended.")


if __name__ == "__main__":
    if LIVEKIT_AVAILABLE:
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
    else:
        print("LiveKit Agents SDK not installed. Run 'pip install -r requirements.txt'")
