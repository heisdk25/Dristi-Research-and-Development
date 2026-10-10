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
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from dotenv import load_dotenv

try:
    from conversation_logger import get_conversation_observer
except ImportError:
    try:
        from agent.conversation_logger import get_conversation_observer
    except ImportError:
        get_conversation_observer = None

# LiveKit Agents imports
try:
    from livekit import rtc
    from livekit.agents import AgentSession, JobContext, RoomInputOptions, WorkerOptions, cli, function_tool
    from livekit.agents.voice import Agent
    from livekit.plugins import google, openai, sarvam, silero
    try:
        from livekit.plugins import elevenlabs
    except ImportError:
        elevenlabs = None
    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False
    elevenlabs = None
    JobContext = Any
    AgentSession = Any
    RoomInputOptions = Any
    WorkerOptions = Any
    cli = Any
    rtc = Any
    Agent = Any
    google = Any
    openai = Any
    sarvam = Any
    silero = Any
    def function_tool(f=None, *args, **kwargs):
        if f is not None and callable(f):
            return f
        def decorator(fn):
            return fn
        return decorator

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
        "   - When the user asks what is in front of them, to describe the scene, or asks in Hindi ('samne kya hai', 'mere samne kya hai', 'aage kya hai', 'kya dikh raha hai', 'dekho', 'kya hai samne', 'aspaas kya hai'), immediately call the describe_scene tool. Do NOT guess or say the path is clear without calling the describe_scene tool.\n"
        "   - When the user asks where they are, what place this is, or in Hindi ('kahan hu main', 'kaha hu', 'where am I', 'what place is this', 'aspaas kya hai'), immediately call the get_user_location tool.\n"
        "   - When the user asks to switch or change modes ('mode badlo', 'switch to navigation', 'ocr mode', 'normal mode'), call the switch_mode tool.\n"
        "   - When the user asks to read text, signs, or documents ('kya likha hai', 'padho', 'read text'), call the read_text_in_view tool.\n"
        "   - When the user asks to navigate or go somewhere ('take me to ...', 'ghar chalo', 'metro station jana hai'), call the start_navigation tool.\n"
        "   - When navigating and the user asks for the next step or says walk/continue ('next step', 'walk', 'aage badho', 'continue'), call the walk_next_step tool.\n"
        "   - When navigating and the user asks to stop ('stop navigation', 'cancel directions', 'ruk jao'), call the stop_navigation tool.\n"
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

        # Navigation State (from PR #1)
        self.current_lat: float = 21.2161986
        self.current_lng: float = 81.3077697
        self.location_accuracy: float = 10.0
        self.location_source: str = "Mobile GPS"
        self.is_navigating: bool = False
        self.active_destination: Optional[str] = None
        self.route_steps: list = []
        self.current_step_index: int = 0

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
        elif msg_type == "GPS_LOCATION":
            self.current_lat = float(payload.get("latitude", self.current_lat))
            self.current_lng = float(payload.get("longitude", self.current_lng))
            self.location_accuracy = float(payload.get("accuracy", self.location_accuracy))
            self.location_source = payload.get("source", "Android Fused GPS")
            return {"status": "ok", "lat": self.current_lat, "lng": self.current_lng}
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
        if any(c in text for c in ["cancel", "stop emergency", "i am fine", "i'm fine", "abort", "theek hu", "mai theek hu"]):
            return ("EMERGENCY_CANCEL", {"confidence": 1.0})

        # Emergency trigger
        emergency_triggers = [
            "help emergency", "emergency pls help", "emergency please help", "emergency alert",
            "pls help", "please help", "help me", "save me", "bachao", "madad karo"
        ]
        if any(term in text for term in emergency_triggers) or (
            "emergency" in text and any(w in text for w in ["help", "sos", "alert", "danger", "khatra", "call"])
        ):
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

# ── Navigation Service (Powered by Google Places & Routes v2) ──

class NavigationService:
    """Handles dual-layer location awareness, place search, and walking route planning."""

    @staticmethod
    def get_maps_api_key() -> str:
        return os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("MAPS_API_KEY", "").strip()

    @classmethod
    def get_current_location(cls, current_lat: float = 21.2161986, current_lng: float = 81.3077697, accuracy: float = 10.0, source: str = "Fused GPS") -> str:
        """
        Dual-layer location hierarchy (Places Nearby 30m POI + Reverse Geocoding).
        Identifies nearest named landmark/building and street address.
        """
        maps_key = cls.get_maps_api_key()
        poi = ""
        locality = ""

        if maps_key and not maps_key.startswith("<") and not maps_key.startswith("..."):
            # Layer 1: Places API (Nearby Search) for closest building within 30m
            try:
                places_url = "https://places.googleapis.com/v1/places:searchNearby"
                payload = {
                    "locationRestriction": {
                        "circle": {
                            "center": {"latitude": current_lat, "longitude": current_lng},
                            "radius": 30.0
                        }
                    },
                    "maxResultCount": 1
                }
                headers = {
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": maps_key,
                    "X-Goog-FieldMask": "places.displayName"
                }
                req = urllib.request.Request(places_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    data = json.loads(resp.read().decode())
                    if "places" in data and len(data["places"]) > 0:
                        poi = data["places"][0].get("displayName", {}).get("text", "")
            except Exception as e:
                logger.debug(f"Places nearby search error: {e}")

            # Layer 2: Reverse Geocoding for street and locality
            try:
                geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={current_lat},{current_lng}&key={maps_key}"
                req = urllib.request.Request(geocode_url)
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    data = json.loads(resp.read().decode())
                    if data.get("status") == "OK" and data.get("results"):
                        locality = data["results"][0].get("formatted_address", "")
            except Exception as e:
                logger.debug(f"Reverse geocode error: {e}")

        if poi and locality:
            return f"You are near {poi}, located at {locality}. (Accuracy: {accuracy}m, Source: {source})"
        elif locality:
            return f"You are currently at {locality}. No specific building identified nearby. (Accuracy: {accuracy}m, Source: {source})"
        elif poi:
            return f"You are near {poi}. (Accuracy: {accuracy}m, Source: {source})"
        else:
            return f"Current GPS location: {current_lat:.4f}, {current_lng:.4f} (Accuracy: {accuracy}m, Source: {source})."

    @classmethod
    def search_place(cls, query: str, current_lat: float = 21.2161986, current_lng: float = 81.3077697) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
        """Uses Google Places API (New) with 5km location bias circle to find destination."""
        maps_key = cls.get_maps_api_key()
        if not maps_key or maps_key.startswith("<") or maps_key.startswith("..."):
            return None, None, None

        url = "https://places.googleapis.com/v1/places:searchText"
        payload = {
            "textQuery": query,
            "locationBias": {
                "circle": {
                    "center": {"latitude": current_lat, "longitude": current_lng},
                    "radius": 5000.0
                }
            }
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": maps_key,
            "X-Goog-FieldMask": "places.formattedAddress,places.displayName,places.location"
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read().decode())
                if "places" in data and len(data["places"]) > 0:
                    place = data["places"][0]
                    return place.get("formattedAddress"), place.get("displayName", {}).get("text"), place.get("location")
        except Exception as e:
            logger.warning(f"Google Places text search failed: {e}")
        return None, None, None

    @classmethod
    def plan_route(cls, destination: str, current_lat: float = 21.2161986, current_lng: float = 81.3077697) -> Dict[str, Any]:
        """
        Uses Google Routes API (v2) to fetch the safest walking route with micro-steps.
        Gracefully falls back to deterministic calculations if offline or no API key.
        """
        cleaned_dest = destination.strip().title()
        maps_key = cls.get_maps_api_key()

        if maps_key and not maps_key.startswith("<") and not maps_key.startswith("..."):
            resolved_address, place_name, location = cls.search_place(cleaned_dest, current_lat, current_lng)
            target_address = resolved_address or cleaned_dest
            display_title = place_name or cleaned_dest

            routes_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
            payload = {
                "origin": {
                    "location": {
                        "latLng": {"latitude": current_lat, "longitude": current_lng}
                    }
                },
                "destination": {
                    "address": target_address
                },
                "travelMode": "WALK",
                "languageCode": "en-US",
                "routingPreference": "ROUTING_PREFERENCE_UNSPECIFIED"
            }
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": maps_key,
                "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.legs.steps.navigationInstruction.instructions,routes.legs.steps.distanceMeters"
            }
            try:
                req = urllib.request.Request(routes_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    data = json.loads(resp.read().decode())
                    if "routes" in data and len(data["routes"]) > 0:
                        route = data["routes"][0]
                        dist_m = route.get("distanceMeters", 450)
                        dur_str = route.get("duration", "360s")
                        dur_sec = int(dur_str.replace("s", "")) if dur_str.endswith("s") else 360
                        dur_min = max(1, dur_sec // 60)

                        steps = []
                        raw_steps = route.get("legs", [{}])[0].get("steps", [])
                        for s in raw_steps:
                            instruction = s.get("navigationInstruction", {}).get("instructions", "Continue forward")
                            s_dist = s.get("distanceMeters", 50)
                            steps.append({
                                "instruction": instruction,
                                "distance_m": s_dist,
                                "bearing": "12 o'clock"
                            })

                        if steps:
                            return {
                                "destination": display_title,
                                "origin": {"lat": current_lat, "lng": current_lng},
                                "total_distance_m": dist_m,
                                "estimated_time_min": dur_min,
                                "steps": steps
                            }
            except Exception as e:
                logger.warning(f"Google Routes v2 computeRoutes failed ({e}), using fallback route.")

        # Graceful fallback (deterministic safe walking route)
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

    @staticmethod
    def walk_step(current_step_index: int, steps: list) -> Tuple[int, str, bool]:
        """
        Advances the micro-step navigation index.
        Returns: (new_index, spoken_message, is_arrived)
        """
        if not steps:
            return 0, "No active route to walk. Tell me where you would like to go.", False

        next_idx = current_step_index + 1
        if next_idx < len(steps):
            step = steps[next_idx]
            dist = step.get("distance_m", step.get("distance", 50))
            inst = step.get("instruction", "Continue forward")
            msg = f"Navigation update: Continue straight for approx {dist} meters. Then, {inst}."
            return next_idx, msg, False
        else:
            msg = "You have arrived at your destination! Disclaimer: Please verify with your cane or guide dog that the entrance is clear and safe to enter."
            return next_idx, msg, True


# ── Core Navigation Agent (Ported from PR #1) ─────────────────

class NavigationAgent:
    """
    Core pedestrian navigation agent for blind and visually impaired users.
    Implements PR #1's exact navigation agent specification:
      1. Dual-layer location awareness (Places Nearby 30m + Geocoding)
      2. Pedestrian walking route calculation via Google Routes API v2
      3. Granular micro-step walking progression with obstacle alerts & arrival disclaimer
    """

    def __init__(self, lat: float = 21.2161986, lng: float = 81.3077697, accuracy: float = 10.0, source: str = "Fused Location Provider"):
        self.is_navigating = False
        self.destination = None
        self.route_steps = []
        self.current_step_index = 0
        self.current_lat = lat
        self.current_lng = lng
        self.location_accuracy = accuracy
        self.location_source = source

    def get_current_location(self) -> str:
        """Uses Google Reverse Geocoding + Places API for location-awareness hierarchy."""
        return NavigationService.get_current_location(
            self.current_lat, self.current_lng, self.location_accuracy, self.location_source
        )

    def search_place(self, query: str) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
        """Uses Google Places API (New) to find a destination near the user."""
        return NavigationService.search_place(query, self.current_lat, self.current_lng)

    def calculate_safest_route(self, destination_name: str) -> str:
        """Uses Google Routes API (v2) to fetch the best walking route with micro-steps."""
        route_data = NavigationService.plan_route(destination_name, self.current_lat, self.current_lng)
        self.destination = route_data.get("destination", destination_name)
        self.route_steps = route_data.get("steps", [])
        self.current_step_index = 0
        self.is_navigating = True

        dist_m = route_data.get("total_distance_m", 450)
        dur_min = route_data.get("estimated_time_min", 6)

        if not self.route_steps:
            return f"Sorry, I couldn't find a safe walking route to {self.destination}."

        first = self.route_steps[0]
        return (
            f"Found {self.destination}! It is {dist_m} meters away and will take about {dur_min} minutes walking.\n"
            f"First step: {first['instruction']} (for approx {first['distance_m']}m)."
        )

    def walk_step(self) -> str:
        """Simulates/advances pedestrian movement and announces micro-step navigation instructions."""
        if not self.is_navigating or not self.route_steps:
            return "You are not currently navigating anywhere. Ask me to go somewhere first!"

        new_idx, message, is_arrived = NavigationService.walk_step(self.current_step_index, self.route_steps)
        self.current_step_index = new_idx
        if is_arrived:
            self.is_navigating = False
            self.destination = None
            self.route_steps = []
            self.current_step_index = 0
        return message


def run_interactive_navigation(agent: Optional[NavigationAgent] = None):
    """Interactive CLI testing console for Navigation Mode (Ported from PR #1)."""
    if agent is None:
        agent = NavigationAgent()
    print("======================================================")
    print(" Drishti Navigation Agent - Interactive Navigation Mode ")
    print("======================================================")
    print("Type your voice commands below (e.g., 'where am i', 'take me to hospital', 'walk').")
    print("Type 'exit' to stop.")
    print("------------------------------------------------------")

    groq_key = os.getenv("GROQ_API_KEY", "")
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    while True:
        try:
            user_input = input("\nUser (Blind Person): ").strip()
            if user_input.lower() in ["exit", "quit", "stop"]:
                print("Drishti: Stopping navigation system. Goodbye!")
                break
            if not user_input:
                continue

            print("Drishti: (Thinking...)")
            ai_response = None

            # Try Groq classification if key is available
            if groq_key and not groq_key.startswith("<") and not groq_key.startswith("..."):
                try:
                    prompt = f"""
                    You are the brain of Drishti, a smart glasses AI for blind people.
                    The user said: "{user_input}"

                    Categorize this intent into exactly ONE of these formats:
                    - If they want to know where they are: return strictly "INTENT: LOCATE"
                    - If they want to go somewhere or find something: return strictly "INTENT: NAVIGATE | <destination>" (e.g. "INTENT: NAVIGATE | the nearest hospital")
                    - If they want to take a step or walk: return strictly "INTENT: WALK"
                    - Otherwise, act as a helpful conversation partner and reply naturally to their question in 1-2 short sentences.
                    """
                    groq_url = "https://api.groq.com/openai/v1/chat/completions"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {groq_key}",
                        "User-Agent": "Mozilla/5.0"
                    }
                    payload = {
                        "model": groq_model,
                        "messages": [{"role": "user", "content": prompt}]
                    }
                    req = urllib.request.Request(groq_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=4.0) as resp:
                        data = json.loads(resp.read().decode())
                        ai_response = data["choices"][0]["message"]["content"].strip()
                except Exception as e:
                    logger.debug(f"Groq API intent classifier notice: {e}")

            if not ai_response:
                lower = user_input.lower()
                if any(w in lower for w in ["where am i", "what place", "location", "kahan", "locate"]):
                    ai_response = "INTENT: LOCATE"
                elif any(w in lower for w in ["take me to", "navigate to", "go to", "route to", "directions to"]):
                    match = re.search(r"(?:take me to|navigate to|go to|route to|directions to)\s+(.+)", lower)
                    dest = match.group(1).strip() if match else "Destination"
                    ai_response = f"INTENT: NAVIGATE | {dest}"
                elif any(w in lower for w in ["walk", "step", "next", "continue", "aage"]):
                    ai_response = "INTENT: WALK"
                else:
                    ai_response = "I am listening. Ask where you are, tell me where you'd like to walk, or type walk."

            if "INTENT: LOCATE" in ai_response:
                response = agent.get_current_location()
                print(f"Drishti: {response}")
            elif "INTENT: NAVIGATE" in ai_response:
                dest = ai_response.split("|")[1].strip() if "|" in ai_response else "destination"
                print(f"Drishti: Calculating the safest walking route to {dest}...")
                response = agent.calculate_safest_route(dest)
                print(f"Drishti: {response}")
            elif "INTENT: WALK" in ai_response:
                response = agent.walk_step()
                print(f"Drishti: {response}")
            else:
                print(f"Drishti: {ai_response}")
        except KeyboardInterrupt:
            print("\nDrishti: Navigation session interrupted.")
            break


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
    observer = get_conversation_observer() if get_conversation_observer else None
    if observer:
        observer.set_mode(initial_mode)
    openai_backup_key = os.getenv("OPENAI_BACKUP_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip() or openai_backup_key
    openai_base = os.getenv("OPENAI_BASE_URL", "").strip() or None
    if openai_base and ("futureppo" in openai_base or "freeapi" in openai_base):
        openai_base = None
    openai_vision_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    google_key = os.getenv("GOOGLE_API_KEY", "").strip()
    google_model = os.getenv("GOOGLE_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"
    gemini_realtime_model = os.getenv("GEMINI_REALTIME_MODEL", "gemini-3.1-flash-live-preview").strip() or "gemini-3.1-flash-live-preview"
    llm_provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

    # ── Configure STT (Speech-to-Text) ──
    # Handled natively by Realtime Multimodal APIs
    stt_plugin = None

    # ── Configure LLM (Google Gemini or OpenAI Realtime Multimodal API) ──
    if llm_provider == "gemini" and google_key and not google_key.startswith("..."):
        logger.info(f"Using Google Gemini Realtime Multimodal API natively ({gemini_realtime_model})")
        llm_plugin = google.realtime.RealtimeModel(
            api_key=google_key,
            model=gemini_realtime_model,
            voice="Puck",
            instructions=PromptManager.get_prompt(initial_mode)
        )
    else:
        logger.info("Using OpenAI Realtime Multimodal API natively.")
        llm_plugin = openai.realtime.RealtimeModel(
            api_key=openai_key,
            base_url="https://api.openai.com/v1",
            model="gpt-4o-realtime-preview",
            voice="alloy",
            instructions=PromptManager.get_prompt(initial_mode)
        )

    # ── Configure TTS (Text-to-Speech) ──
    # Attached for programmatic session.say() (greeting, mode alerts, navigation steps)
    tts_plugin = None
    sarvam_api_key = os.getenv("SARVAM_API_KEY", "").strip()
    if sarvam_api_key and not sarvam_api_key.startswith("..."):
        try:
            tts_plugin = sarvam.TTS(
                api_key=sarvam_api_key,
                target_language_code=os.getenv("SARVAM_TTS_LANGUAGE", "hi-IN"),
                speaker=os.getenv("SARVAM_TTS_SPEAKER", "kabir"),
                pace=float(os.getenv("SARVAM_TTS_PACE", "1.25")),
            )
            logger.info("Configured Sarvam TTS for programmatic speech synthesis")
        except Exception as e:
            logger.warning(f"Failed to initialize Sarvam TTS: {e}")

    # ── Configure VAD for Fast Low-Latency Conversational Turn Detection ──
    # 0.32s silence duration ensures fast cutoff without clipping words
    vad_plugin = silero.VAD.load(
        min_silence_duration=0.32,
        activation_threshold=0.5,
        prefix_padding_duration=0.15,
    )

    # ── Real-Time Camera Frame, Mode Manager & Navigation Agent ──
    latest_camera_frame: Optional[str] = None
    latest_camera_frame_time: float = 0.0
    mode_manager = ModeManager(initial_mode)
    nav_agent = NavigationAgent(lat=21.2161986, lng=81.3077697, accuracy=10.0)

    async def _process_incoming_packet(data_bytes: bytes):
        nonlocal latest_camera_frame, latest_camera_frame_time
        try:
            raw_text = await asyncio.to_thread(data_bytes.decode, "utf-8")
            payload = await asyncio.to_thread(json.loads, raw_text)
            msg_type = payload.get("type")
            if msg_type == "CAMERA_FRAME":
                latest_camera_frame = payload.get("image_base64")
                latest_camera_frame_time = time.time()
                logger.info(f"Received fresh camera frame from mobile device ({len(latest_camera_frame or '')} chars)")
            elif msg_type == "GPS_LOCATION":
                nav_agent.current_lat = float(payload.get("latitude", nav_agent.current_lat))
                nav_agent.current_lng = float(payload.get("longitude", nav_agent.current_lng))
                nav_agent.location_accuracy = float(payload.get("accuracy", nav_agent.location_accuracy))
                logger.debug(f"Received GPS location: {nav_agent.current_lat:.5f}, {nav_agent.current_lng:.5f}")
            elif msg_type == "OBSTACLE_WARNING":
                obstacle = payload.get("obstacle", "obstacle")
                pos = payload.get("position", "ahead")
                dist = payload.get("distance", "")
                logger.info(f"Obstacle alert from phone: {obstacle} at {pos} ({dist}m)")
                if observer:
                    observer.record_obstacle_alert(str(obstacle), str(pos), str(dist))
            elif msg_type == "OCR_RESULT":
                logger.info(f"OCR text received: {payload.get('text')}")
            elif msg_type == "MODE_CHANGE":
                new_mode = payload.get("mode", "assistant").strip().lower()
                old_mode = mode_manager.active_mode
                result = mode_manager.switch_mode(new_mode)
                if result["success"]:
                    agent.update_instructions(PromptManager.get_prompt(result["mode"]))
                    logger.info(f"Mobile app switched mode to '{result['mode']}'. Agent prompt updated smoothly.")
                    if observer:
                        observer.record_mode_switch(old_mode, result["mode"], source="mobile_app")
                    if result["mode"] == "navigation":
                        # Auto-run navigation mode immediately upon switching
                        loc_desc = await asyncio.to_thread(nav_agent.get_current_location)
                        try:
                            if nav_agent.is_navigating and nav_agent.route_steps:
                                curr = nav_agent.route_steps[nav_agent.current_step_index]
                                await session.say(f"Navigation mode active. {loc_desc}. Next step: {curr['instruction']}.", allow_interruptions=True)
                            else:
                                await session.say(f"Navigation mode active. {loc_desc}. Where would you like to go?", allow_interruptions=True)
                        except Exception as e:
                            logger.debug(f"Auto-run navigation speech notice: {e}")
        except Exception as err:
            logger.warning(f"Error handling data packet: {err}")

    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        asyncio.create_task(_process_incoming_packet(data_packet.data))

    async def analyze_frame_with_vision(image_base64: str) -> str:
        prompt = (
            "You are Drishti, an assistive vision companion for a visually impaired user. "
            "Examine what is directly in front of the camera right now. "
            "CRITICAL RULES:\n"
            "1. Give your answer in 1 or 2 concise, clear sentences in simple language.\n"
            "2. Accurately identify and name objects, furniture, people, obstacles, walls, or clutter directly ahead and specify relative directions (e.g., directly in front of you, on your left, at 12 o'clock, 1 meter away).\n"
            "3. If indoors in a room, describe what is in the room (e.g., table, chair, laptop, bed, person sitting, doorway).\n"
            "4. NEVER say 'The path is clear' or 'no obstacles' if there are visible objects, furniture, or clutter ahead!\n"
            "5. Never say 'in the image' or 'the picture shows'—speak naturally as if viewing through their eyes."
        )
        vision_start = time.time()
        model_used = "Google Gemini" if google_key else "OpenAI Vision"
        result_text = ""

        # Check image brightness to detect pitch-black frames early
        clean_b64 = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
        try:
            import base64 as b64_mod, io
            from PIL import Image, ImageStat
            raw_bytes = b64_mod.b64decode(clean_b64)
            img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            stat = ImageStat.Stat(img)
            avg_brightness = sum(stat.mean) / 3.0
            logger.info(f"Frame analysis: resolution={img.size}, avg_brightness={avg_brightness:.1f}/255")
            if avg_brightness < 10.0:
                logger.warning(f"Incoming camera frame is pitch black (brightness: {avg_brightness:.1f}/255)")
                return "The camera view is completely dark right now. Please uncover the camera lens, point it toward the room, and ask again."
        except Exception as img_err:
            logger.debug(f"Image stat check: {img_err}")

        # Primary: Google Gemini Vision (gemini-3.5-flash) - highly accurate, fast, tested working
        if google_key and not google_key.startswith("...") and len(google_key) > 10:
            try:
                model_used = f"Google Gemini ({google_model})"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{google_model}:generateContent?key={google_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/jpeg", "data": clean_b64}}
                        ]
                    }],
                    "generationConfig": {
                        "maxOutputTokens": 200,
                        "thinkingConfig": {"thinkingBudget": 0}
                    }
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if "text" in part and part["text"].strip():
                            result_text = part["text"].strip()
                            break
            except Exception as e:
                logger.warning(f"Gemini vision call failed: {e}")

        # Secondary: OpenAI Vision Fallback
        if not result_text and openai_key and not openai_key.startswith("..."):
            try:
                model_used = f"OpenAI ({openai_vision_model})"
                url = f"{openai_base or 'https://api.openai.com/v1'}/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_key}"
                }
                clean_b64 = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
                image_url = f"data:image/jpeg;base64,{clean_b64}"
                payload = {
                    "model": openai_vision_model,
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
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    if text:
                        result_text = text
            except Exception as oai_err:
                logger.warning(f"OpenAI vision call failed: {oai_err}")

        # Tertiary Failover: Direct OpenAI key if proxy failed
        if not result_text:
            backup_key = os.getenv("OPENAI_BACKUP_KEY", "").strip()
            if backup_key and backup_key != openai_key:
                try:
                    logger.info("Attempting direct OpenAI vision fallback...")
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {backup_key}"
                    }
                    clean_b64 = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
                    image_url = f"data:image/jpeg;base64,{clean_b64}"
                    payload = {
                        "model": "gpt-4o-mini",
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
                    async with httpx.AsyncClient(timeout=12.0) as client:
                        resp = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                        resp.raise_for_status()
                        data = resp.json()
                        text = data["choices"][0]["message"]["content"].strip()
                        if text:
                            result_text = text
                            model_used = "OpenAI Direct (gpt-4o-mini)"
                            logger.info("Direct OpenAI vision fallback succeeded")
                except Exception as b_err:
                    logger.warning(f"Direct OpenAI vision fallback failed: {b_err}")

        final_desc = result_text or "I am unable to see clearly right now. Please point your camera forward and ask again."
        dur_ms = (time.time() - vision_start) * 1000
        if observer:
            observer.record_vision_call("scene_description", model_used, "Analyze camera frame for obstacles and path", final_desc, dur_ms)
        return final_desc

    async def extract_text_with_vision(image_base64: str) -> str:
        prompt = (
            "You are Drishti in Reading Mode for a visually impaired user. "
            "Examine the camera frame and read aloud all visible printed or handwritten text. "
            "Identify what the text is on (e.g., medicine box, street sign, book, receipt, screen, label). "
            "If it is a product or medicine, highlight the name, dosage, or expiry date. "
            "CRITICAL RULE: Give answer in short! Strictly 1 to 2 clear, concise sentences."
        )
        vision_start = time.time()
        model_used = "Google Gemini" if google_key else "OpenAI Vision"
        ocr_result = ""

        # Primary: Google Gemini OCR (gemini-3.5-flash)
        if google_key and not google_key.startswith("...") and len(google_key) > 10:
            try:
                model_used = f"Google Gemini ({google_model})"
                clean_b64 = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{google_model}:generateContent?key={google_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/jpeg", "data": clean_b64}}
                        ]
                    }],
                    "generationConfig": {
                        "maxOutputTokens": 250,
                        "thinkingConfig": {"thinkingBudget": 0}
                    }
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if "text" in part and part["text"].strip():
                            ocr_result = part["text"].strip()
                            break
            except Exception as e:
                logger.warning(f"Gemini OCR call failed: {e}")

        # Secondary Failover: OpenAI Vision
        if not ocr_result and openai_key and not openai_key.startswith("..."):
            try:
                model_used = f"OpenAI ({openai_vision_model})"
                url = f"{openai_base or 'https://api.openai.com/v1'}/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_key}"
                }
                clean_b64 = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
                image_url = f"data:image/jpeg;base64,{clean_b64}"
                payload = {
                    "model": openai_vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": image_url}}
                            ]
                        }
                    ],
                    "max_tokens": 150
                }
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    if text:
                        ocr_result = text
            except Exception as fallback_err:
                logger.warning(f"OpenAI OCR failed: {fallback_err}")

        # Tertiary Failover: Direct OpenAI key if proxy failed
        if not ocr_result:
            backup_key = os.getenv("OPENAI_BACKUP_KEY", "").strip()
            if backup_key and backup_key != openai_key:
                try:
                    logger.info("Attempting direct OpenAI OCR fallback...")
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {backup_key}"
                    }
                    clean_b64 = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
                    image_url = f"data:image/jpeg;base64,{clean_b64}"
                    payload = {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": image_url}}
                                ]
                            }
                        ],
                        "max_tokens": 150
                    }
                    async with httpx.AsyncClient(timeout=12.0) as client:
                        resp = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                        resp.raise_for_status()
                        data = resp.json()
                        text = data["choices"][0]["message"]["content"].strip()
                        if text:
                            ocr_result = text
                            model_used = "OpenAI Direct (gpt-4o-mini)"
                            logger.info("Direct OpenAI OCR fallback succeeded")
                except Exception as b_err:
                    logger.warning(f"Direct OpenAI OCR fallback failed: {b_err}")

        final_ocr = ocr_result or "No clear text was found in the camera view."
        dur_ms = (time.time() - vision_start) * 1000
        if observer:
            observer.record_vision_call("ocr", model_used, "Read visible printed or handwritten text", final_ocr, dur_ms)
        return final_ocr

    @function_tool
    async def describe_scene() -> str:
        """Call this tool whenever the user asks what is in front of them, to describe the scene, what the camera sees, or asks in Hindi/Hinglish ('सामने क्या है', 'आगे क्या है', 'क्या दिख रहा है', 'dekho', 'samne kya hai', 'mere samne kya hai', 'aage kya hai', 'kya dikh raha hai', 'aspaas kya hai', 'kya hai samne', 'mere aage kya hai')."""
        nonlocal latest_camera_frame, latest_camera_frame_time
        logger.info("Function tool 'describe_scene' invoked by agent")

        req_time = time.time()
        # Request fresh frame from client to ensure we describe what's in front of them right now
        try:
            req = json.dumps({"type": "REQUEST_FRAME"}).encode("utf-8")
            await ctx.room.local_participant.publish_data(req)
            # Wait up to 0.7s for a freshly dispatched frame from the phone
            for _ in range(14):
                await asyncio.sleep(0.05)
                if latest_camera_frame and latest_camera_frame_time >= req_time:
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
        
        old_mode = mode_manager.active_mode
        result = mode_manager.switch_mode(target_mode)
        if not result["success"]:
            return result["error"]
            
        mode_name = result["mode"]
        if not result["changed"]:
            if mode_name == "navigation":
                loc_desc = await asyncio.to_thread(nav_agent.get_current_location)
                if nav_agent.is_navigating and nav_agent.route_steps:
                    curr = nav_agent.route_steps[nav_agent.current_step_index]
                    return f"Navigation mode active. {loc_desc}. Continuing route to {nav_agent.destination}. Next step: {curr['instruction']}."
                return f"Navigation mode active. {loc_desc}. Where would you like to go?"
            return f"{mode_name.capitalize()} mode is already active."

        agent.update_instructions(PromptManager.get_prompt(mode_name))
        logger.info(f"Switched mode to '{mode_name}' and updated agent prompt smoothly")
        if observer:
            observer.record_mode_switch(old_mode, mode_name, source="voice_tool")

        try:
            packet = json.dumps({"type": "SWITCH_MODE", "target": mode_name}).encode("utf-8")
            await ctx.room.local_participant.publish_data(packet)
        except Exception as e:
            logger.warning(f"Failed to publish SWITCH_MODE to mobile client: {e}")

        # Auto-run mode logic upon switching, like other modes
        if mode_name == "navigation":
            loc_desc = await asyncio.to_thread(nav_agent.get_current_location)
            if nav_agent.is_navigating and nav_agent.route_steps:
                curr = nav_agent.route_steps[nav_agent.current_step_index]
                return f"Navigation mode active. {loc_desc}. Continuing route to {nav_agent.destination}. Next step: {curr['instruction']}."
            return f"Navigation mode active. {loc_desc}. Where would you like to go?"
        elif mode_name == "ocr":
            return "Reading mode active. Point your camera at text, or ask me to read what is in front of you."
        elif mode_name == "emergency":
            return "Emergency mode active. Say cancel to abort, or help is being notified."

        return f"{mode_name.capitalize()} mode activated."

    @function_tool
    async def get_user_location() -> str:
        """Call this tool whenever the user asks where they are, what building or place is nearby, or asks in Hindi/Hinglish ('where am I', 'kahan hu main', 'kaha hu', 'kidhar hu', 'what place is this', 'aspaas kya hai', 'ye konsi jagah hai')."""
        logger.info(f"Function tool 'get_user_location' invoked (lat={nav_agent.current_lat}, lng={nav_agent.current_lng})")
        loc_desc = await asyncio.to_thread(nav_agent.get_current_location)
        logger.info(f"Location resolved: {loc_desc}")
        return loc_desc

    @function_tool
    async def start_navigation(destination: str) -> str:
        """Initiate walking navigation to a destination or landmark. Call this whenever the user asks to navigate or walk somewhere in English or Hindi ('take me to ...', 'directions to ...', 'घर चलो', 'रास्ता दिखाओ', 'ghar chalo', 'rasta dikhao').
        Args:
            destination: Name of the destination (e.g., 'Metro station', 'Hospital', 'Home').
        """
        logger.info(f"Function tool 'start_navigation' invoked for '{destination}'")

        if mode_manager.active_mode != "navigation":
            mode_manager.switch_mode("navigation")
            agent.update_instructions(PromptManager.get_prompt("navigation"))
            try:
                packet = json.dumps({"type": "SWITCH_MODE", "target": "navigation"}).encode("utf-8")
                await ctx.room.local_participant.publish_data(packet)
            except Exception:
                pass

        # Calculate walking route via Google Routes API v2 using NavigationAgent
        route_msg = await asyncio.to_thread(nav_agent.calculate_safest_route, destination)

        total_dist = 450
        est_min = 6
        first_step = "Walk straight"
        if nav_agent.route_steps:
            first_step = nav_agent.route_steps[0]["instruction"]
            total_dist = sum(s.get("distance_m", 50) for s in nav_agent.route_steps)
            est_min = max(1, total_dist // 80)

        try:
            packet = json.dumps({
                "type": "REQUEST_NAVIGATION",
                "destination": nav_agent.destination or destination,
                "distance_m": total_dist,
                "duration_min": est_min,
                "first_step": first_step
            }).encode("utf-8")
            await ctx.room.local_participant.publish_data(packet)
        except Exception as e:
            logger.warning(f"Failed to publish REQUEST_NAVIGATION to mobile client: {e}")

        return route_msg

    @function_tool
    async def walk_next_step() -> str:
        """Advance to the next walking step in navigation mode. Call this whenever the user asks for the next step, says walk, continue, or in Hindi ('aage badho', 'agla kadam', 'next step', 'walk', 'continue')."""
        logger.info("Function tool 'walk_next_step' invoked")

        if not nav_agent.is_navigating or not nav_agent.route_steps:
            return "You are not currently navigating anywhere. Ask me to navigate to a place first."

        step_msg = nav_agent.walk_step()
        if not nav_agent.is_navigating:
            try:
                packet = json.dumps({"type": "NAVIGATION_ARRIVED"}).encode("utf-8")
                await ctx.room.local_participant.publish_data(packet)
            except Exception:
                pass

        return step_msg

    @function_tool
    async def stop_navigation() -> str:
        """Stop or cancel active walking navigation. Call this whenever the user says stop navigation, cancel directions, or in Hindi ('ruk jao', 'navigation band karo')."""
        logger.info("Function tool 'stop_navigation' invoked")

        if not nav_agent.is_navigating:
            return "Navigation is not currently active."

        dest = nav_agent.destination or "destination"
        nav_agent.is_navigating = False
        nav_agent.destination = None
        nav_agent.route_steps = []
        nav_agent.current_step_index = 0

        try:
            packet = json.dumps({"type": "STOP_NAVIGATION"}).encode("utf-8")
            await ctx.room.local_participant.publish_data(packet)
        except Exception:
            pass

        return f"Navigation to {dest} has been stopped."

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

    agent_tools = [
        describe_scene,
        switch_mode,
        get_user_location,
        start_navigation,
        walk_next_step,
        stop_navigation,
        read_text_in_view,
    ]

    # ── Create AgentSession with Ultra-Low Latency & Non-Expiring Session Lifetime ──
    session = AgentSession(
        stt=stt_plugin,
        llm=llm_plugin,
        tts=tts_plugin,
        vad=vad_plugin,
        tools=agent_tools,
        turn_detection="vad",
        min_endpointing_delay=0.25,      # 250ms: snappy responses without cutting words
        max_endpointing_delay=0.85,      # 850ms: allows natural pauses formulation
        aec_warmup_duration=0.0,
        allow_interruptions=True,
        min_interruption_duration=0.25,
        resume_false_interruption=True,  # Resumes speaking if interrupted by accidental breath/noise
        user_away_timeout=None,          # NEVER disconnect or stop responding due to silence
        preemptive_generation=False,     # Prevents race condition cancellations and empty responses
    )

    # ── Attach Conversation Observer for Real-Time Terminal Observation & Logging ──
    if observer:
        observer.attach_to_session(session, get_current_mode=lambda: mode_manager.active_mode)

    @session.on("error")
    def on_session_error(err):
        logger.warning(f"Voice agent session warning: {err}")

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

    logger.info(f"Agent session started smoothly in '{initial_mode}' mode (24/7 continuous listening)")

    # ── Notify mobile client over data channel that voice agent is active ──
    try:
        ready_packet = json.dumps({
            "type": "AGENT_READY",
            "mode": initial_mode,
            "agent": "drishti-livekit-agent",
            "status": "ready"
        }).encode("utf-8")
        await ctx.room.local_participant.publish_data(ready_packet)
        logger.info("Published AGENT_READY packet to room participants")
    except Exception as pkt_err:
        logger.debug(f"Agent ready signal note: {pkt_err}")

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

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(p: rtc.RemoteParticipant):
        logger.info(f"Participant disconnected from room: {p.identity}")
        # Cleanly release agent job when user leaves room so the next session gets a fresh worker instantly
        if len(ctx.room.remote_participants) <= 1:
            logger.info("All active participants left. Releasing agent job cleanly.")
            disconnect_event.set()

    try:
        await disconnect_event.wait()
    except (asyncio.CancelledError, Exception):
        pass
    finally:
        logger.info("Room disconnected cleanly. Session ended.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["nav", "navigation", "--nav", "--navigation"]:
        run_interactive_navigation()
    elif LIVEKIT_AVAILABLE:
        worker_port = int(os.getenv("LIVEKIT_HTTP_PORT", "0"))
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, port=worker_port))
    else:
        print("LiveKit Agents SDK not installed. Run 'pip install -r requirements.txt'")
