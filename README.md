# Project Drishti: Research and Development

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Kotlin](https://img.shields.io/badge/Kotlin-1.9+-7F52FF.svg?logo=kotlin&logoColor=white)](https://kotlinlang.org)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org)
[![LiveKit](https://img.shields.io/badge/LiveKit-WebRTC-FF4F00.svg)](https://livekit.io)
[![BOM Cost](https://img.shields.io/badge/Hardware%20BOM-%3C%2460%20USD-brightgreen.svg)](#hardware-bom)

> **Voice-First Multimodal Assistive Companion for Visually Impaired Persons (VIPs)**  
> Engineered with a dual-tier edge-cloud architecture: **sub-400ms on-device reflex hazard detection** coupled with **low-latency cloud conversational intelligence**.

---

## 📑 Repository Structure

`
├── hackbios-neuraX/             # Complete Production Codebase
│   ├── android/                 # Native Android App (Kotlin, CameraX, YOLOv8n TFLite, LiveKit)
│   ├── agent/                   # Cloud Multimodal Agent (Python, LiveKit Agents, Sarvam, Gemini/Groq)
│   ├── token-server/            # Room Token Dispatch Server (Node.js / Express / FastAPI)
│   ├── esp32-firmware/          # ESP32-CAM Firmware (C++/Arduino, MJPEG Wi-Fi SoftAP Streamer)
│   └── docs/                    # Codebase Guides & Architectural Flowcharts
│
├── hackathon_strategy/          # Hackathon Strategic & Research Ops Compendium
│   ├── DRISHTI_EXISTING_FEATURES_AND_UPGRADES.md       # Master Inventory & Upgrades Roadmap
│   ├── DRISHTI_RESEARCH_OPS_COMPARISON_AND_OPTIMIZATIONS.md # Literature Gap Analysis & 7 Upgrades
│   ├── HACKATHON_SPONSORS_INTEGRATION_PLAN.md          # Gemini 2.0, ElevenLabs, Vultr, Tiger Data
│   └── DRISHTI_NON_TECH_EXPLAINER_AND_PITCH_GUIDE.md   # Pitch Scripts & Non-Tech Analogies
│
├── paper_memories/              # Deep Extraction Memories from 8 Benchmark Research Papers
│   ├── INDEX_ASSISTIVE_RESEARCH_COMPENDIUM.md
│   ├── MEMORY_01_SOUND_BASED_NAVIGATION_MALAEKAH.md
│   ├── MEMORY_02_LVLM_WEARABLE_VISION_ASSIST_BAIG.md
│   ├── MEMORY_03_OPSISVISION_HYBRID_EDGE_CLOUD_TSINAFORNIOTIS.md
│   ├── MEMORY_04_DRISHT_DUAL_STREAM_MOBILE_LOTEY.md
│   ├── MEMORY_05_EDGE_CLOUD_INTELLIGENT_CANE_MA.md
│   ├── MEMORY_06_BHARAT_ASSIST_EMBEDDED_VISION_CHAWAN.md
│   ├── MEMORY_07_LOW_COST_MULTIFUNCTIONAL_GLASSES_KRAL.md
│   └── MEMORY_08_SEMANTIC_VISUAL_SLAM_WEARABLE_CHEN.md
│
├── papers/                      # Original PDF Research Papers (Peer-Reviewed Literature)
├── DRISHTI_SYSTEM_MEMORY.md     # Single Source of Truth System Architecture & Math Specs
├── drishti_architecture.mermaid # Full Mermaid System Topology
└── drishti_architecture_archify.html # Interactive Visual Architecture Explorer
`

---

## ⚡ Core Architecture

Drishti solves the assistive computing trade-off through a decoupled **two-tier architecture**:

1. **Tier 1: Ultra-Fast Edge Reflex Loop (Sub-400ms, Completely Offline)**
   - **Object Detection:** YOLOv8n Float16 ( \times 320$, 4 CPU threads + NNAPI delegate) executing in -38\text{ ms}$.
   - **Monocular Depth Heuristic:**  = \frac{0.8}{\text{safeHeight}}$ with clock-face directional mapping (*10, 12, 2 o'clock*).
   - **Immediate Haptic & Voice Reflex:** High-priority local Android TTS with audio ducking interrupts background chatter for critical hazards ($< 2.5\text{ m}$).
   - **Inertial Fall Detection:** Accelerometer impact spike ($> 25\text{ m/s}^2$) followed by stillness ($< 11.5\text{ m/s}^2$) triggers a 15-second SOS countdown.

2. **Tier 2: Cloud Multimodal Conversational Loop (Ambient Intelligence)**
   - **WebRTC Transport:** LiveKit ultra-low latency real-time audio and video streaming.
   - **DataChannel Telemetry:** Periodic 40% JPEG frames ( \times 240$) and hazard alerts sent to the cloud worker.
   - **Conversational Reasoning:** Multi-provider fallback across Groq LPU (GPT-OSS-120B, $<300\text{ ms}$ TTFT), Google Gemini 2.0 Flash, and OpenAI GPT-4o.
   - **Vernacular Speech:** Sarvam AI STT (saaras:v4) and TTS (ulbul:v3) tailored for Indian-accented English and Hindi. Enforces a strict 1–2 sentence brevity limit.

---

## 🛠️ Hardware Bill of Materials (BOM < )

| Component | Role | Approximate Cost |
| :--- | :--- | :--- |
| **Android Smartphone** | Edge Compute (YOLOv8n, Sensor Fusion, TTS, LiveKit) | User-owned / Base device |
| **ESP32-CAM Node** | Wearable chest/chest-mount camera module | ~.50 |
| **3.7V LiPo Battery + TP4056** | Power supply for wearable node | ~.00 |
| **3D-Printed / Belt Clip Enclosure** | Mechanical housing | ~.00 |
| **Earphone / Headset** | Spatial audio output & microphone | ~.00 |
| **Total BOM** | Ultra-accessible, mass-manufacturable | **~.50 – .00** |

---

## 🚀 Quickstart Guide

### 1. Token Dispatch Server
`ash
cd hackbios-neuraX/token-server
npm install
npm run dev
# Running on http://localhost:3000
`

### 2. Python Multimodal Agent
`ash
cd hackbios-neuraX/agent
python -m venv venv
# On Windows:
.\venv\Scripts\activate
pip install -r requirements.txt
python drishti_agent.py dev
`

### 3. Android Edge Application
1. Open hackbios-neuraX/android in **Android Studio Hedgehog / Iguana / Jellyfish**.
2. Sync Gradle dependencies.
3. Configure your server URL in DrishtiService.kt or pp-config.json.
4. Build and deploy to an Android device (API 26+).

---

## 🏆 Hackathon Sponsors Integration Ready

- **Google Gemini 2.0 Flash:** Native multimodal visual QA via LiveKit video channel.
- **ElevenLabs:** Hyper-realistic emotional speech synthesis with conversational interrupts.
- **Vultr Cloud Compute:** High-performance container hosting for the agent worker with global edge low-latency routing.
- **Tiger Data:** Ultra-low latency time-series telemetry store for fall detection and spatial logs.

---

## 📄 License
This project is licensed under the MIT License — see the LICENSE file for details.
