# Project Drishti: 24-Hour Hackathon Sponsor Integration & Architecture Strategy

> **Context:** Strategic integration roadmap incorporating the 4 hackathon sponsors (**Gemini API**, **ElevenLabs**, **Vultr**, and **Tiger Data**) into Project Drishti without altering any physical hardware components.  
> **Source Baseline:** [DRISHTI_SYSTEM_MEMORY.md](file:///E:/HAckbios-R&D/DRISHTI_SYSTEM_MEMORY.md) & [hackbios-neuraX](file:///E:/HAckbios-R&D/hackbios-neuraX) Codebase.  
> **Status:** Concrete Implementation Plan & Sponsor Pitch Strategy.  
> **Author:** Antigravity Research Ops & System Architecture Team  
> **Date:** October 9, 2026  

---

## 1. Executive Summary & Sponsor Track Alignment

During a 24-hour hackathon, winning project submissions maximize eligibility across sponsor prize tracks while presenting a coherent, production-ready narrative. By integrating all four sponsors into **Project Drishti's production codebase ([hackbios-neuraX](file:///E:/HAckbios-R&D/hackbios-neuraX))**, we enhance the system's conversational intelligence, emotional warmth, cloud scalability, and telemetry observability—**while keeping the exact same physical hardware bill of materials ($<\$60$ Android + ESP32-CAM)**.

```
+----------------------------------------------------------------------------------------------------+
|                                 HACKATHON SPONSOR ARCHITECTURE MAPPING                             |
|                                                                                                    |
|    SPONSOR            ROLE IN DRISHTI                       TARGET FILE IN CODEBASE                |
|  ───────────          ──────────────────────                ──────────────────────────────────     |
|  1. Gemini API        Multimodal Brain (Flash / Live)       agent/drishti_agent.py                 |
|                       Sub-400ms visual QA; medicine triage. (google.LLM: gemini-2.0-flash)         |
|                                                                                                    |
|  2. ElevenLabs        Conversational Cloud Voice            agent/drishti_agent.py                 |
|                       Empathetic, hyper-realistic voice for (elevenlabs.TTS plugin alongside       |
|                       dialogue & fall check-in ("Are you OK") local Android LocalTTS.kt)           |
|                                                                                                    |
|  3. Vultr             Cloud Host & Orchestration            token-server/ & agent/                 |
|                       Hosts FastAPI & LiveKit agent worker  (FastAPI JWT server + Agent worker     |
|                       on a lean, low-cost CPU cloud VPS.    with multi-candidate endpoint chain)   |
|                                                                                                    |
|  4. Tiger Data        Time-Series Caregiver Telemetry       android/ai/drishti/emergency/ &        |
|                       & Real-Time Latency Dashboard         token-server/main.py                   |
|                       Postgres time-series store for IMU,   (AlertSender.kt + Telemetry logger)    |
|                       fall events, GPS, and latency logs.                                          |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Deep-Dive: Sponsor Services & Strategic Integration

### 2.1 Sponsor 1: Google Gemini API (Multimodal Intelligence)

#### Where it fits in Drishti:
* **The Multimodal Brain:** Direct integration in [agent/drishti_agent.py](file:///E:/HAckbios-R&D/hackbios-neuraX/agent/drishti_agent.py).
* **Already Scaffolded in Codebase:**
  In `agent/drishti_agent.py` lines 334–336, Gemini 2.0 Flash is already configured:
  ```python
  elif provider == "google" and google_key:
      llm_plugin = google.LLM(model="gemini-2.0-flash")
      logger.info("Using Google Gemini LLM (gemini-2.0-flash)")
  ```
* **Core Responsibilities:**
  1. **Conversational Scene Reasoning (`describe_scene` tool):** Inspects incoming 320x240 JPEG frames dispatched every 2.0s over LiveKit DataChannel. Explains navigable walking corridors and obstacles around construction.
  2. **Reading & Text Understanding (`read_text_in_view` tool):** Deciphers medicine packaging, expiry dates, street signs, and store names.
  3. **High-Stakes Safety Triage ("Medicine Triage"):** Verifies pharmaceutical labels, dosage instructions, and issues spoken disclaimers if packaging is blurry.
  4. **Strict Brevity Enforcement:** Formats answers strictly into 1 to 2 short sentences as required by the prompt manager.

#### Recommended Models & Technical Implementation:
* **Primary Engine: `gemini-2.0-flash` (via Google GenAI SDK / LiveKit Google Plugin):**
  * Time-to-First-Token (TTFT) is $\approx 250-450\text{ ms}$.
  * Low cost, high context window, excellent OCR fidelity.
* **Optional Advanced Option: Gemini Multimodal Live API (WebSocket / WebRTC):**
  * Gemini 2.0 native audio-in / audio-out streaming allows the client to pipe microphone audio directly into Gemini and receive real-time audio streams back, skipping separate STT and TTS pipeline hops.

#### Hackathon Pitch Point:
> *"By adopting Gemini 2.0 Flash, Drishti achieves lightning-fast conversational visual reasoning under 400 ms TTFT, enabling true real-time assistive dialogues where visually impaired users receive crisp 1-to-2 sentence answers about their surroundings without awkward pauses."*

---

### 2.2 Sponsor 2: ElevenLabs (Conversational Voice & Emotional Warmth)

#### Where it fits in Drishti:
* **The Human-Like Cloud Voice:** Synthesizes conversational answers, detailed scene narratives, and empathetic emergency prompts in [agent/drishti_agent.py](file:///E:/HAckbios-R&D/hackbios-neuraX/agent/drishti_agent.py).
* **The Architectural Split (The "Audio Duality Pitch"):**
  * **Tier 1 (Offline Hazard Reflex):** Handled strictly by [LocalTTS.kt](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/audio/LocalTTS.kt) on Android. When a car approaches ($d < 2.5\text{ m}$), latency must be $<150\text{ ms}$ without cellular dependence, using `flush = true`.
  * **Tier 2 (Cloud Conversational Dialogue):** Handled by **ElevenLabs Streaming Models** (`eleven_flash_v2` or `eleven_turbo_v2_5`). Delivers expressive, empathetic, non-robotic narration when describing surroundings, reading books, or performing the gentle fall check-in: *"Emergency alert initiated. Say cancel to abort, or help is being notified."*

#### Technical Implementation:
* Integrate the LiveKit ElevenLabs plugin or streaming endpoint into `drishti_agent.py`:
  ```python
  from livekit.plugins import elevenlabs
  tts_plugin = elevenlabs.TTS(
      model="eleven_flash_v2",
      voice="Rachel",
      latency=1
  )
  ```
* Chunked PCM/Opus streaming directly into the LiveKit audio track buffer.

#### Hackathon Pitch Point:
> *"Assistive technology often feels clinical and cold. Drishti introduces an intentional audio duality: an instantaneous, rugged Android LocalTTS for life-or-death obstacle alerts, paired with ElevenLabs' warm, empathetic voice for comforting human-like companionship and gentle fall check-ins."*

---

### 2.3 Sponsor 3: Vultr (Cloud Infrastructure & Compute Hosting)

#### Where it fits in Drishti:
* **Central Cloud Server:** Hosts the complete backend stack in [token-server/](file:///E:/HAckbios-R&D/hackbios-neuraX/token-server) and [agent/](file:///E:/HAckbios-R&D/hackbios-neuraX/agent):
  1. **FastAPI Token Server (`token-server/main.py`):** JWT authentication, user profile management, session handshake, and automatic LiveKit agent dispatching (`CreateAgentDispatchRequest`).
  2. **LiveKit SFU / Media Gateway:** Real-time WebRTC media routing (audio tracks + video DataChannels).
  3. **LiveKit Agent Worker (`agent/drishti_agent.py`):** Pipes audio/video packets between LiveKit, Gemini Flash, and ElevenLabs.

#### Network Failover Compatibility:
* The Android client ([LiveKitClient.kt](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/audio/LiveKitClient.kt)) already includes a candidate failover list:
  ```kotlin
  val candidates = linkedSetOf(
      primaryUrl, // Points to Vultr Cloud VPS IP/domain
      "http://127.0.0.1:8000",
      "http://10.113.162.33:8000",
      "http://10.0.2.2:8000"
  )
  ```
  Pointing `preferenceManager.tokenServerUrl` to the Vultr public IP/domain connects the Android app to the cloud in production while preserving local USB/emulator fallbacks!

#### Recommended Hardware Configuration:
* **Vultr Cloud Compute (High Frequency or Regular Performance):**
  * $2\text{ vCPUs}$, $4\text{ GB RAM}$, $64\text{ GB NVMe SSD}$ ($\approx \$20 - \$24/\text{month}$).
* **Why No Expensive GPUs Are Needed:**
  * Neural detection (`yolov8n_float16.tflite`) runs 100% on the user's smartphone SoC.
  * Heavy vision-language reasoning is handled by Gemini's API endpoints.
  * ElevenLabs handles TTS synthesis.
  * Therefore, the Vultr instance strictly acts as an ultra-efficient, lightweight network router and orchestrator!

#### Hackathon Pitch Point:
> *"Drishti proves that state-of-the-art assistive AI does not require prohibitively expensive cloud GPU clusters. By leveraging Vultr's lean, high-frequency CPU instances for lightweight WebRTC orchestration, we keep operational hosting costs under pennies per user per month."*

---

### 2.4 Sponsor 4: Tiger Data (Time-Series Telemetry & Caregiver Portal)

#### Where it fits in Drishti:
* **Time-Series Telemetry & Health Monitoring Store:**
  * Uses Tiger Data (PostgreSQL-based Time-Series Engine) to store high-frequency kinematic signals and operational telemetry.
* **What Data Gets Stored in Tiger Data:**
  1. **Fall Verification Signatures:** Tri-axial acceleration $\mathbf{a}(t)$, impact magnitude $> 25.0\text{ m/s}^2$, and stillness verification from [FallDetector.kt](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/sensors/FallDetector.kt).
  2. **Live Kinematic Telemetry:** Step cadence, GPS latitude/longitude breadcrumbs from [LocationProvider.kt](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/sensors/LocationProvider.kt).
  3. **Per-Stage Latency Benchmarking Logs:** End-to-end telemetry recording actual measured runtimes:
     * $T_{\text{capture}}$, $T_{\text{tflite\_infer}}$ ($20-38\text{ ms}$), $T_{\text{proximity}}$ ($<2\text{ ms}$), $T_{\text{webrtc\_uplink}}$, $T_{\text{gemini\_ttft}}$, $T_{\text{elevenlabs\_tts}}$.
  4. **Caregiver Event Logs:** Real-time emergency trigger logs dispatched by [AlertSender.kt](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/emergency/AlertSender.kt).

#### Why This Fixes a Critical Paper Weakness:
* The original manuscript relied heavily on theoretical latency decompositions (Table 3).
* With **Tiger Data**, we can show **actual, empirical measured latency distributions across hundreds of live frames and voice turns**, plotted in real time on a clean Caregiver/Developer Dashboard!

#### Hackathon Pitch Point:
> *"With Tiger Data's time-series engine, Drishti transforms from an isolated wearable into an interconnected safety ecosystem. Caregivers can view real-time location and fall alerts, while developers have millisecond-by-millisecond time-series observability of the entire edge-cloud latency budget."*

---

## 3. Architecture Diagram: Hackathon Sponsor Stack

```mermaid
flowchart TB
    subgraph HARDWARE["Tier 0: Hardware Peripherals (Unchanged)"]
        ESP32["ESP32-CAM Node<br/><i>OV2640 VGA MJPEG (mjpeg_streamer.ino)</i>"]
        CAMX["Phone CameraX<br/><i><500ms Fallback Hot Handover (CameraManager.kt)</i>"]
        IMU["Phone 3-Axis IMU<br/><i>Accelerometer a(t) @ 100Hz (FallDetector.kt)</i>"]
        MIC["Earphone Mic<br/><i>Audio Input (Opus 48kHz)</i>"]
        SPEAKER["Earphone Speaker<br/><i>Binaural Audio Output</i>"]
    end

    subgraph EDGE["Tier 1: Android Native Edge Core (DrishtiService.kt - 100% Offline)"]
        MUX["Camera Manager (Frame Multiplexer)"]
        YOLO["TFLite YOLOv8n Float16 @ 320x320<br/><b>20-38ms on NNAPI/CPU (TFLiteDetector.kt)</b>"]
        PROX["ObstacleClassifier & Clock Face<br/><i>d = 0.8/safeHeight | 10/12/2 o'clock</i>"]
        FALL["FallDetector & EmergencyMonitor<br/><i>Impact > 25m/s² → 15s Voice Window</i>"]
        LOCALTTS["LocalTTS Engine (Android TextToSpeech)<br/><b>Priority Safety Speech Override (flush=true)</b>"]
        ALERT_SENDER["AlertSender.kt<br/><i>SMS (Maps) | WhatsApp | ACTION_CALL | Siren</i>"]
    end

    subgraph VULTR["Vultr Cloud Compute Instance (Ubuntu 24.04 LTS)"]
        FASTAPI["FastAPI Token Server (token-server/main.py)<br/><i>JWT Auth + Auto-Dispatch (CreateAgentDispatchRequest)</i>"]
        LIVEKIT["LiveKit WebRTC Server<br/><i>UDP/SRTP Audio & DataChannel Router</i>"]
        WORKER["LiveKit Agent Worker (agent/drishti_agent.py)<br/><i>PromptManager (Strict 1-2 Sentence Brevity)</i>"]
    end

    subgraph SPONSOR_AI["Cloud Generative AI Services"]
        GEMINI["Google Gemini 2.0 Flash API<br/><b>Multimodal Brain: describe_scene, read_text_in_view</b>"]
        ELEVEN["ElevenLabs Streaming TTS<br/><b>Empathetic Conversational Voice & Fall Check-In</b>"]
    end

    subgraph SPONSOR_DATA["Tiger Data (Time-Series PostgreSQL)"]
        TIGER_DB[("Tiger Data Time-Series Store<br/><i>Impact Telemetry, GPS Breadcrumbs, Latency Metrics</i>")]
        DASHBOARD["Caregiver & Telemetry Web Portal<br/><i>Live GPS, Health State & Latency Charts</i>"]
    end

    %% Edge Flows
    ESP32 --> MUX
    CAMX -.-> MUX
    MUX --> YOLO --> PROX --> LOCALTTS --> SPEAKER
    IMU --> FALL
    FALL -.->|Urgent Alert| LOCALTTS
    FALL --> ALERT_SENDER

    %% Vultr WebRTC Bridge
    MIC --> LIVEKIT
    MUX -.->|DataChannel 320x240 JPEG Base64 (every 2.0s)| LIVEKIT
    FASTAPI <--> LIVEKIT
    LIVEKIT <--> WORKER
    WORKER <--> GEMINI
    WORKER --> ELEVEN --> LIVEKIT --> SPEAKER

    %% Telemetry & Tiger Data
    ALERT_SENDER -->|Emergency GPS / Fall Payload| FASTAPI --> TIGER_DB
    PROX -.->|OBSTACLE_WARNING Latency| FASTAPI --> TIGER_DB
    TIGER_DB --> DASHBOARD

    %% Styles
    classDef hardware fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef edge fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    classDef vultr fill:#003366,stroke:#0072ff,stroke-width:2px,color:#ffffff;
    classDef ai fill:#3b0764,stroke:#c084fc,stroke-width:2px,color:#ffffff;
    classDef tiger fill:#78350f,stroke:#f59e0b,stroke-width:2px,color:#ffffff;

    class ESP32,CAMX,IMU,MIC,SPEAKER hardware;
    class MUX,YOLO,PROX,FALL,LOCALTTS,ALERT_SENDER edge;
    class FASTAPI,LIVEKIT,WORKER vultr;
    class GEMINI,ELEVEN ai;
    class TIGER_DB,DASHBOARD tiger;
```

---

## 4. Code-Level Implementation Recipes for `hackbios-neuraX`

### 4.1 Mod 1: Vultr Deployment of `token-server` and `agent`
Deploy the existing `token-server/` and `agent/` onto a Vultr Ubuntu 24.04 instance with Docker:

```dockerfile
# Dockerfile for Vultr Deployment
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ffmpeg libopus-dev build-essential
COPY token-server/requirements.txt ./token-reqs.txt
COPY agent/requirements.txt ./agent-reqs.txt
RUN pip install --no-cache-dir -r token-reqs.txt -r agent-reqs.txt
COPY token-server/ ./token-server/
COPY agent/ ./agent/
EXPOSE 8000
CMD ["uvicorn", "token-server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### 4.2 Mod 2: Activating Gemini 2.0 Flash in `agent/drishti_agent.py`
In `agent/.env`, set:
```ini
LLM_PROVIDER=google
GOOGLE_API_KEY=your_gemini_api_key_here
```
In `drishti_agent.py`, the existing LLM factory automatically instantiates Gemini:
```python
elif provider == "google" and google_key:
    llm_plugin = google.LLM(model="gemini-2.0-flash")
    logger.info("Using Google Gemini LLM (gemini-2.0-flash)")
```
For visual scene Q&A, `analyze_frame_with_vision()` in `drishti_agent.py` sends the Base64 frame to Gemini with the strict 1-to-2 sentence prompt:
```python
payload = {
    "model": "gemini-2.0-flash",
    "contents": [
        {"parts": [{"text": "Describe the camera view concisely in 1 to 2 short sentences."},
                   {"inline_data": {"mime_type": "image/jpeg", "data": image_base64}}]}
    ]
}
```

---

### 4.3 Mod 3: Adding ElevenLabs TTS Plugin to `agent/drishti_agent.py`
In `agent/drishti_agent.py`, configure ElevenLabs as an alternate TTS provider:
```python
from livekit.plugins import elevenlabs

if os.getenv("TTS_PROVIDER", "sarvam").lower() == "elevenlabs":
    tts_plugin = elevenlabs.TTS(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
        model="eleven_flash_v2",
        voice="Rachel"
    )
```

---

### 4.4 Mod 4: Tiger Data Time-Series Database Schema & Telemetry Endpoint
Tiger Data utilizes PostgreSQL with time-series capabilities. Add to `token-server/main.py`:

```sql
-- Tiger Data Time-Series Telemetry Table
CREATE TABLE user_telemetry_stream (
    timestamp        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id          VARCHAR(64) NOT NULL,
    impact_magnitude DOUBLE PRECISION NOT NULL,
    gps_lat          DOUBLE PRECISION,
    gps_lon          DOUBLE PRECISION,
    trigger_reason   VARCHAR(64),
    fall_state       VARCHAR(32) DEFAULT 'NORMAL'
);

-- Tiger Data Latency Benchmark Table
CREATE TABLE pipeline_latency_benchmarks (
    timestamp        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_id           VARCHAR(64) NOT NULL,
    tflite_infer_ms  DOUBLE PRECISION NOT NULL,
    proximity_ms     DOUBLE PRECISION NOT NULL,
    webrtc_rtt_ms    DOUBLE PRECISION NOT NULL,
    gemini_ttft_ms   DOUBLE PRECISION NOT NULL,
    total_turn_ms    DOUBLE PRECISION NOT NULL
);

CREATE INDEX idx_telemetry_time ON user_telemetry_stream (timestamp DESC);
CREATE INDEX idx_latency_time ON pipeline_latency_benchmarks (timestamp DESC);
```

In `token-server/main.py`:
```python
@app.post("/telemetry/emergency")
async def log_emergency_event(payload: dict):
    # Ingests payload from Android AlertSender.kt
    # Writes into Tiger Data PostgreSQL
    ...
```

---

## 5. 24-Hour Hackathon Implementation Timeline

| Hours | Phase | Target Deliverables |
|---|---|---|
| **00:00 – 03:00** | **Cloud & DB Provisioning** | 1. Spin up Vultr CPU droplet (Ubuntu 24.04).<br>2. Provision Tiger Data Postgres instance & run DDL tables.<br>3. Obtain API keys for Gemini (Google AI Studio) and ElevenLabs. |
| **03:00 – 08:00** | **Backend Core on Vultr** | 1. Deploy `token-server/main.py` on Vultr with auto-dispatch.<br>2. Run `drishti_agent.py` configured with Gemini 2.0 Flash + ElevenLabs Flash.<br>3. Connect LiveKit room pipeline. |
| **08:00 – 14:00** | **Edge Android & ESP32 Integration** | 1. Connect Android app to Vultr token server IP.<br>2. Verify `yolov8n_float16.tflite` continues running locally @ 20-38 ms.<br>3. Pipe emergency fall logs from `AlertSender.kt` to Tiger Data. |
| **14:00 – 18:00** | **Caregiver Dashboard & Latency Charts** | 1. Build simple web dashboard (React / HTML).<br>2. Query Tiger Data to display live GPS location, fall alert timeline, and real-time latency waterfall chart! |
| **18:00 – 21:00** | **End-to-End Testing & Demos** | 1. Test offline obstacle warnings (verify LocalTTS works with airplane mode on).<br>2. Test online scene Q&A via Gemini Flash + ElevenLabs voice.<br>3. Simulate phone drop to verify fall trigger + Tiger Data log. |
| **21:00 – 24:00** | **Pitch Deck & Sponsor Submission** | 1. Record 2-minute video demo.<br>2. Submit to all 4 sponsor tracks with explicit callouts for Gemini, ElevenLabs, Vultr, and Tiger Data! |

---

## 6. The Winning Hackathon Pitch Script (2 Minutes)

* **Hook (0:00 - 0:30):**  
  *"Over 2.2 billion people live with visual impairment, and injurious falls happen 3 times more often than among sighted individuals. Commercial solutions cost between $2,500 and $4,500, while smartphone apps freeze completely during subway or network dropouts. Meet Project Drishti: a voice-first assistive companion for under $60 that never leaves you unprotected."*

* **The Architecture & Offline Safety (0:30 - 1:00):**  
  *"Drishti is built on an intentional dual-tier architecture. On the edge, our Float16 YOLOv8 model runs in 20 to 38 milliseconds on your smartphone, detecting obstacles and falls 100% offline with zero-latency Android LocalTTS alerts using clock-face directions like 'Car at 2 o'clock, 2 meters away'. If the user drops their phone, our smart motion window gives a 15-second voice window to cancel before triggering an emergency SMS and call."*

* **The Sponsor Superpowers (1:00 - 1:40):**  
  *"For conversational scene understanding, we tap into our sponsor stack:*
  * *Hosted on a lean, high-frequency **Vultr** cloud instance without needing expensive GPUs.*
  * *Powered by **Google Gemini 2.0 Flash**, which visually analyzes navigation corridors and safely reads complex medicine labels in under 400 milliseconds.*
  * *Voiced by **ElevenLabs'** hyper-realistic streaming models, delivering comforting human-like dialogue and empathetic fall check-ins.*
  * *Monitored by **Tiger Data**, which logs real-time IMU kinematic time-series and enables a live Caregiver Portal showing actual, empirical millisecond-level latency benchmarks."*

* **The Closing (1:40 - 2:00):**  
  *"Drishti bridges the gap between rugged, offline safety reflexes and human-like conversational intelligence—at a price anyone can afford. Thank you."*
