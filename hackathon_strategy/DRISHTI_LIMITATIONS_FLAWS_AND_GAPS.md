# Project Drishti: Critical Analysis of Limitations, Architectural Flaws, and Research Gaps

> **Document Type:** Forensic Technical Audit & Gap Analysis Compendium  
> **Target System:** Project Drishti (Voice-First Multimodal Companion for Visually Impaired Persons)  
> **Source Evidence:** [DRISHTI_SYSTEM_MEMORY.md](file:///E:/HAckbios-R&D/DRISHTI_SYSTEM_MEMORY.md), [mksinha01/hackbios-neuraX](file:///E:/HAckbios-R&D/hackbios-neuraX) Codebase, and 8 Benchmark Research Papers  
> **Hardware Constraint:** **BOM < $60, Fixed Hardware** (ESP32-CAM, Android smartphone, earphones). No added sensors or boards.  
> **Author:** Research Operations (Research Ops) Architecture Team  
> **Date:** October 9, 2026  

---

## Executive Summary

While Project Drishti presents an innovative, cost-effective (<$60 BOM) dual-tier architecture that bridges offline sub-300ms edge reflexes with cloud MLLM conversational intelligence, a rigorous code audit and comparative literature review reveals **significant architectural flaws, algorithmic vulnerabilities, human-factor gaps, and safety hazards**.

This document provides a forensic, evidence-backed breakdown of these flaws across **6 core operational dimensions**, citing exact codebase files, mathematical formulas, and real-world failure scenarios for Visually Impaired Persons (VIPs).

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PROJECT DRISHTI: SYSTEM GAP & FLAW TAXONOMY                     │
├────────────────────────────────┬───────────────────────────────────────────────────────┤
│ 1. ALGORITHMIC & VISION FLAWS  │ Class-agnostic distance heuristic, negative obstacle  │
│                                │ blindness, traffic light color blindness, no tracking │
├────────────────────────────────┼───────────────────────────────────────────────────────┤
│ 2. HARDWARE & PERIPHERAL GAPS  │ Wi-Fi SoftAP breaks 4G data, subnet brute-force scan, │
│                                │ ESP32 battery drain, GC heap allocation thrashing     │
├────────────────────────────────┼───────────────────────────────────────────────────────┤
│ 3. SAFETY & EMERGENCY FLAWS    │ Rebound-false fall triggers, WhatsApp intent failure, │
│                                │ Android 12+ background dialer & SMS restrictions      │
├────────────────────────────────┼───────────────────────────────────────────────────────┤
│ 4. HUMAN FACTORS & AUDIO UI    │ Auditory masking, lack of 3D binaural spatial audio,  │
│                                │ cognitive lexical load, audio collision / overlap     │
├────────────────────────────────┼───────────────────────────────────────────────────────┤
│ 5. CLOUD & PIPELINE DEFICITS   │ Hardcoded LiveKit JWT secrets in client, mock routes, │
│                                │ low-res 40% JPEG blur, continuous mic eavesdropping   │
├────────────────────────────────┼───────────────────────────────────────────────────────┤
│ 6. LOCALIZATION & MAPPING GAPS │ GPS indoor blindness, zero floor/elevation awareness, │
│                                │ lack of semantic visual-inertial odometry / SLAM      │
└────────────────────────────────┴───────────────────────────────────────────────────────┘
```

---

# PART I: Algorithmic & Computer Vision Flaws

### 1.1 The Class-Agnostic Monocular Distance Heuristic (d = 0.8 / safeHeight)
* **Code Reference:** [`ObstacleClassifier.kt: lines 109-113`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/vision/ObstacleClassifier.kt#L109-L113)
  ```kotlin
  fun estimateDistance(normalizedHeight: Float): Float {
      val safeHeight = normalizedHeight.coerceIn(0.05f, 1.0f)
      val distance = 0.8f / safeHeight
      return (distance * 10).toInt() / 10.0f
  }
  ```
* **The Flaw:** This formula assumes that every detected object has the same physical real-world height and that normalized bounding box height is universally proportional to distance by a static scalar (0.8 m).
* **Failure Dynamics & Safety Hazards:**
  1. **Small Hazard Underestimation (False Sense of Safety):**
     - A small dog, chair, or fire hydrant (physical height ~0.4 m) at a real-world distance of 1.0 m occupies ~20% of the vertical frame (safeHeight = 0.20).
     - Calculated distance: d = 0.8 / 0.20 = 4.0 meters.
     - **Result:** An immediate tripping hazard right at the user's shins is classified as "far away" (4.0 m) and completely bypasses the high-priority hazard warning threshold (< 2.5 m).
  2. **Large Hazard Overestimation (False Brake Reflex):**
     - A large city bus or truck (physical height ~3.5 m) at a safe distance of 10.0 m occupies ~50% of the vertical frame (safeHeight = 0.50).
     - Calculated distance: d = 0.8 / 0.50 = 1.6 meters.
     - **Result:** The user is startled with an urgent "Bus very close center" warning, triggering sudden evasive panic when the bus is actually across the street.
  3. **Orientation / Pose Sensitivity:**
     - A person standing upright has height ~1.7 m. A person crouching, tying their shoe, or lying down has height ~0.5 m. Drishti reports the crouching person as 3x further away than the standing person at identical distances.

---

### 1.2 Zero Torso Pitch / Phone Tilt Compensation
* **The Flaw:** In real-world walking, a user's chest pitches forward and backward by 10° to 25° during normal gait cycle. Furthermore, if the user holds their smartphone, pitch and roll vary continuously.
* **Failure Dynamics:**
  - Standard pinhole geometry requires the optical horizon to compute ground plane distance:
    d = (h_camera - h_obstacle) / tan(theta_pitch + alpha)
  - Drishti uses zero IMU orientation angles. When the user tilts the camera down by 15° to look at the ground, bounding boxes shift upward and expand, causing distance estimates to fluctuate erratically by ±100% on every footstep.

---

### 1.3 Complete Blindness to "Negative Obstacles" (The #1 Fatal VIP Hazard)
* **Code Reference:** [`ObstacleClassifier.kt: lines 32-50`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/vision/ObstacleClassifier.kt#L32-L50)
* **The Flaw:** Drishti filters strictly for 14 positive COCO classes:
  `person, bicycle, car, motorcycle, bus, truck, traffic light, fire hydrant, stop sign, bench, dog, chair, couch, potted plant`.
* **The Blind Spot:** In orientation and mobility (O&M) research for VIPs, the most dangerous hazards are **negative obstacles**:
  - Open manholes and missing sewer grates.
  - Descending staircases and downward steps.
  - Drop-offs, curb edges, and subway platform borders.
  - Potholes and open construction trenches.
* **Consequence:** Drishti provides 0% protection against drop-offs. A blind user walking directly toward a 10-foot open trench or down an unexpected flight of subway stairs will receive a message: "Path clear directly ahead", leading to catastrophic physical injury.

---

### 1.4 Traffic Light Color Blindness at Pedestrian Crossings
* **Code Reference:** [`ObstacleClassifier.kt: line 38`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/vision/ObstacleClassifier.kt#L38)
* **The Flaw:** COCO label 9 is `traffic light`. YOLO outputs a bounding box for `traffic light`, but does not classify whether the light is **RED, AMBER, or GREEN**.
* **Safety Hazard:**
  - When approaching an intersection, Drishti announces: "Caution, traffic light about 3.2 meters center."
  - The blind user cannot tell if it is safe to cross. If the user interprets the prompt as an indication of a pedestrian crossing and walks out during a Red signal, the failure is life-threatening.

---

### 1.5 Frame-by-Frame Inference without Temporal Tracking (No Kalman Filter / ByteTrack)
* **The Flaw:** Inference runs independently on each frame without object identity tracking across time.
* **Failure Dynamics:**
  1. **Alert Flicker & Jitter:** If a car is detected with confidence 0.52 on frame t, drops to 0.47 on frame t+1 due to slight motion blur, and returns to 0.53 on frame t+2, the TTS audio engine triggers repeated, jerky warnings: "Car ahead... Car ahead..."
  2. **Zero Time-to-Collision (TTC) & Velocity Awareness:**
     - A stationary parked motorcycle at 3.5 m is treated with the exact same alert logic as an oncoming motorcycle accelerating at 40 km/h at 3.5 m!
     - In the case of the speeding vehicle, the user has < 300 ms before impact, but Drishti cannot compute velocity (delta d / delta t) or project impending collision trajectories.

---

### 1.6 Extreme Spatial Downsampling (320x320 Input Resolution)
* **Code Reference:** [`TFLiteDetector.kt: lines 24-25`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/vision/TFLiteDetector.kt#L24-L25)
* **The Flaw:** Camera frames are resized to 320x320 pixels for YOLOv8n Float16.
* **Failure Dynamics:**
  - Overhead tree branches at eye level, low-hanging electrical cables, construction scaffolding poles, and low curbs occupy only 2 to 6 pixels at 320x320.
  - These critical VIP hazards vanish in feature map striding, leaving the user vulnerable to severe upper-body and head collisions.

---

# PART II: Hardware & Peripheral Interface Realities

### 2.1 The ESP32-CAM Wi-Fi SoftAP vs. 4G/5G Cellular Data Conflict
* **Code Reference:** [`Esp32StreamClient.kt: lines 35-77`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/camera/Esp32StreamClient.kt#L35-L77)
* **The Flaw:** The ESP32-CAM hosts a local Wi-Fi Access Point (SoftAP) or joins a local ad-hoc network to transmit MJPEG video. The Android phone connects to this Wi-Fi network.
* **The Operating System Conflict:**
  - In modern Android (Android 10+), when a smartphone connects to a Wi-Fi network with **No Internet Access** (the local ESP32 stream), Android's default network routing either:
    1. Prompts the user "This network has no internet. Disconnect?" and drops the Wi-Fi connection automatically.
    2. Routes **ALL** device IP packets through the Wi-Fi interface, immediately cutting off cellular 4G/5G mobile data.
  - **Result:** The moment the wearable ESP32 camera connects, the phone loses internet connectivity. Tier 2 (LiveKit WebRTC, Groq, Gemini, Sarvam AI) immediately crashes or disconnects unless Android's `ConnectivityManager` explicitly requests a multi-network socket binding using `NetworkCapabilities.TRANSPORT_CELLULAR`.

---

### 2.2 Subnet Brute-Force Socket Exhaustion in autoDiscoverEsp32Ip
* **Code Reference:** [`Esp32StreamClient.kt: lines 150-160`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/camera/Esp32StreamClient.kt#L150-L160)
  ```kotlin
  val deferreds = (1..254).map { i ->
      async {
          val testIp = "$prefix.$i"
          ...
          val scanClient = OkHttpClient.Builder().connectTimeout(800, TimeUnit.MILLISECONDS).build()
          scanClient.newCall(request).execute()
      }
  }
  ```
* **The Flaw:** If the default ESP32 IP is unreachable, the client launches **254 concurrent OkHttpClient socket connections** across the entire /24 subnet simultaneously.
* **Consequences:**
  - Spawning 254 simultaneous socket connection attempts on an Android device causes file descriptor exhaustion (`EMFILE: Too many open files`), heavy CPU thread context switching, and Wi-Fi radio saturation, stalling the main UI thread and freezing background services.

---

### 2.3 ESP32-CAM Battery Life & Thermal Throttling
* **Hardware Reality:** The ESP32-CAM running continuous Wi-Fi transmission at +20 dBm with the OV2640 sensor streaming MJPEG draws ~180 to 260 mA at 5V.
* **Limitations:**
  - A compact wearable 500 mAh LiPo battery is completely drained in **75 to 110 minutes**.
  - Without passive heat sinks or active thermal management, the ESP32 module exceeds 65°C in warm climates, causing camera sensor thermal noise, frame drops (< 4 FPS), and eventual brownout resets.

---

### 2.4 Android Heap GC Churn on Every Video Frame
* **Code References:** [`TFLiteDetector.kt: line 84`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/vision/TFLiteDetector.kt#L84), [`Esp32StreamClient.kt: lines 109-110`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/camera/Esp32StreamClient.kt#L109-L110)
* **The Flaw:** On every single frame:
  1. `Esp32StreamClient` calls `frameBuffer.toByteArray()` and `BitmapFactory.decodeByteArray()`.
  2. `TFLiteDetector` calls `Bitmap.createScaledBitmap(bitmap, 320, 320, true)`.
* **Impact:** This allocates hundreds of megabytes of temporary Bitmap memory per minute, forcing Android's ART garbage collector to trigger continuous GC pause events (15–40ms pauses), leading to frame stutter and jittery response times on entry-level Android devices.

---

# PART III: Safety, Emergency & Fall Detection Vulnerabilities

### 3.1 Flawed Fall Detection State Machine (Immediate False Positives)
* **Code Reference:** [`FallDetector.kt: lines 58-76`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/sensors/FallDetector.kt#L58-L76)
* **The Flaw:** The state machine requires an impact (> 25.0 m/s²), followed by *any single reading* < 11.5 m/s² within 2000ms.
* **Why this Fails in the Real World:**
  - After any sudden impact or shock (e.g., throwing phone on a couch, sitting down heavily on a wooden bench, dropping phone on a carpeted floor, or jumping down a single step), the physical rebound immediately returns the phone to near-1g gravity (~9.8 m/s²) on the very next sensor reading (10–20ms later).
  - Because 9.8 < 11.5, line 67 **immediately evaluates to TRUE on the first post-impact sample**.
  - **Result:** The system triggers an emergency fall siren and SMS countdown on routine non-fall impacts. True fall detection biomechanics require **sustained stillness** (standard deviation of magnitude sigma < 0.5 m/s²) for at least 1.5 to 2.0 continuous seconds.

---

### 3.2 WhatsApp Intent Failure During Emergencies
* **Code Reference:** [`AlertSender.kt: lines 67-79`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/emergency/AlertSender.kt#L67-L79)
* **The Flaw:** Launching a `https://api.whatsapp.com/send` intent opens the WhatsApp application with the message pre-filled in the text box. **It does NOT send the message automatically.**
* **The Fatal Scenario:** An incapacitated, unconscious, or visually impaired user lying on the ground after a fall cannot unlock the phone, locate the WhatsApp interface, and tap the green send arrow. The emergency message sits unsent in an open app.

---

### 3.3 Android Background Execution & Calling Restrictions
* **Code Reference:** [`AlertSender.kt: lines 49, 56`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/emergency/AlertSender.kt#L49-L56)
* **The Flaws:**
  1. `SmsManager.getDefault()` is deprecated in Android 12+ (API 31). On modern multi-SIM Android devices, it frequently fails or throws exceptions without an explicit Subscription ID.
  2. Launching phone calls (`ACTION_CALL`) or activities from a background service while the phone screen is locked is restricted by Android's **Background Activity Launch Restrictions (BALR)** (Android 10+), requiring high-priority notification trampoline interaction.

---

# PART IV: Human Factors, Audio Ergonomics & Cognitive Load

### 4.1 Auditory Masking of Crucial Ambient Environmental Cues
* **The Problem:** Blind individuals rely heavily on passive echolocation and acoustic cues:
  - Echo reflections from walls, shop fronts, and corridors to judge open doorways.
  - Tire noise, engine pitch, and pedestrian footsteps to perceive oncoming traffic.
* **Drishti's Vulnerability:**
  - Continuous verbal speech output ("Caution, car about 2.5 meters center... Person at your 10 o'clock...") drowns out subtle environmental acoustic cues.
  - If a user wears standard in-ear earphones, conductive occlusion physically blocks ambient sound, creating an acoustic isolation hazard.

---

### 4.2 High Cognitive Lexical Load (Spoken Words vs. 3D Binaural Spatial Audio)
* **Comparison:**
  - **Spoken Text:** Hearing "Obstacle at 10 o'clock, 2 meters" requires the brain's Wernicke's area to lexically parse language, decode clock-face orientation, and mentally map it to body space (Cognitive latency ~300 to 450 ms).
  - **Binaural 3D Audio:** Hearing a 3D spatial sound cue (an audio pulse panned with Head-Related Transfer Functions / HRTF directly to the left ear) is processed by the brain's auditory cortex reflexively in **< 40 ms**.
* **The Gap:** Drishti uses monaural spoken text for all spatial alerts, forcing continuous cognitive processing on the user during high-stress navigation.

---

### 4.3 Audio Collision & Voice Contention
* **The Conflict:**
  - Tier 1 runs Android local TTS (`LocalTTS.kt`).
  - Tier 2 runs Cloud streaming voice over LiveKit (`drishti_agent.py` using Sarvam AI Kabir voice).
* **The Flaw:** Although `LocalTTS` implements an alert interrupt flag (`flush = true`), if the cloud agent is speaking a scene description while a sudden edge hazard alert occurs, the user experiences jarring voice switching, audio overlap, or volume ducking stutter.

---

# PART V: Cloud Architecture, Networking & Security Vulnerabilities

### 5.1 Critical Security Vulnerability: Hardcoded Admin Secret in Client Code
* **Code Reference:** [`LiveKitClient.kt: lines 432-433`](file:///E:/HAckbios-R&D/hackbios-neuraX/android/app/src/main/java/ai/drishti/audio/LiveKitClient.kt#L432-L433)
  ```kotlin
  val apiKey = "APIP9k9XrcGvovw"
  val apiSecret = "86UkWnwzmmzUSGqYubq3ID1vCTpSVANBkooQ83NEaYG"
  ```
* **The Vulnerability:**
  - The live administrative API Secret for the LiveKit Cloud project is hardcoded directly in client Kotlin code as an offline fallback token generator.
  - Anyone decompiling the Android APK using standard tools (`jadx-gui`, `apktool`) can extract this secret, granting complete administrative control to join arbitrary rooms, eavesdrop on user microphone and camera streams, dispatch rogue agents, and generate unauthorized tokens.

---

### 5.2 Navigation Route is a Hardcoded Mock in NavigationService
* **Code Reference:** [`drishti_agent.py: lines 250-260`](file:///E:/HAckbios-R&D/hackbios-neuraX/agent/drishti_agent.py#L250-L260)
* **The Flaw:** Drishti's cloud navigation engine has **no real mapping backend**.
  - Regardless of whether the user requests "Navigate to AIIMS Hospital", "Take me to the subway", or "Guide me to the kitchen", the service returns the exact same hardcoded 450-meter, 3-step mock route!
  - It does not integrate Google Directions API, Mapbox Pedestrian Routing, or OpenStreetMap (OSRM).

---

### 5.3 Severe Image Compression Blur on DataChannel (320x240 @ 40% JPEG)
* **The Problem:** In order to keep WebRTC DataChannel packet sizes < 15 KB, the Android client sends downsampled 320x240 JPEG images at 40% quality.
* **The Failure:**
  - In OCR Mode, when a user holds up a medicine box to read dosage/expiry, or a ₹10 vs ₹500 banknote, the fine print is reduced to a blurry pixel artifact.
  - Gemini 2.0 Flash and GPT-4o vision models hallucinate or fail completely when trying to read text from this compressed thumbnail.

---

### 5.4 Continuous Open Microphone (Lack of Wake-Word / Push-to-Talk)
* **The Problem:** LiveKit audio streaming keeps the phone microphone continuously open.
* **The Flaws:**
  1. **Privacy Intrusion:** All ambient conversations, financial transactions at shop counters, and private phone calls are continuously streamed to cloud servers.
  2. **Accidental Triggering:** Street noise, bus conductor calls, or passing pedestrian voices trigger Silero VAD (0.28 s cutoff) and cause the AI companion to interrupt with unprompted answers.

---

# PART VI: Indoor Navigation & Localization Deficits

### 6.1 Complete Blindness Indoors (GPS Dead Zones)
* **The Reality:** Standard GPS satellites require direct line-of-sight. Inside indoor structures—airports, subway stations, hospitals, shopping malls, university campuses—GPS accuracy degrades to ±15 to 50 meters or drops out entirely.
* **The Gap:** Drishti provides zero indoor localization. It cannot:
  - Identify what floor or corridor the user is on.
  - Guide the user to an elevator, restroom, or emergency exit.
  - Recognize room number plaques or doorway thresholds without manual OCR trigger.
* **Literature Benchmark:** State-of-the-art assistive literature (e.g., Chen et al. [Memory 08], Lotey et al. [Memory 04]) deploys **Semantic Visual-Inertial SLAM** or BLE beacon RSSI trilateration to maintain centimeter-accurate indoor navigation.

---

# PART VII: Comprehensive Literature Gap & Benchmark Matrix

The table below contrasts Project Drishti's current implementation against the 8 landmark assistive research papers in the compendium:

| Dimension / Capability | Project Drishti (Current Baseline) | Landmark Research Benchmark | Leading Paper Reference |
| :--- | :--- | :--- | :--- |
| **Distance Estimation** | Static d = 0.8 / safeHeight (Class-Agnostic, Scale-Blind) | Class-conditional regression + Ground-plane homography | Lotey et al. (Memory 04) & Kral et al. (Memory 07) |
| **Negative Obstacles** | **0% Blind** (Detects only 14 positive COCO classes) | Downward plane depth segmentation & edge drop-off line detection | Malaekah et al. (Memory 01) & Ma et al. (Memory 05) |
| **Traffic Light Color** | Detects box only (No color awareness) | HSV upper/lower mask slicer or dedicated light-state classifier | Lotey et al. (Memory 04) |
| **Dynamic Velocity / TTC** | Static frame-by-frame (0 velocity awareness) | ByteTrack / Kalman filter with Time-to-Collision (TTC = d / v) | Chen et al. (Memory 08) |
| **Audio Modality** | Monaural Spoken Words (300-450 ms lexical lag) | HRTF 3D Binaural Spatial Audio Clicks (< 50 ms instinctive reflex) | Malaekah et al. (Memory 01) |
| **Fall Detection** | 2-sample rebound heuristic (High false positives) | Biomechanical impact + Sustained stillness (sigma < 0.5 m/s²) | Ma et al. (Memory 05) |
| **Navigation Engine** | Static Hardcoded Mock (450m, 3 steps) | Dynamic OSRM / Google Directions Pedestrian Waypoints | Baig et al. (Memory 02) |
| **Indoor Localization** | 100% GPS-dependent (Fails indoors) | Semantic Visual SLAM / ORB-SLAM3 on edge keyframes | Chen et al. (Memory 08) |
| **Wearable Network** | SoftAP Wi-Fi blocks Android 4G mobile data | Bluetooth LE control + Bound Cellular Network Capabilities | Tsinaforniotis et al. (Memory 03) |
| **Security Architecture** | Hardcoded LiveKit JWT Secret in client code | Ephemeral backend token minting with token revocation | Enterprise SecOps Baseline |

---

# PART VIII: Zero-Hardware-Change Remediation Roadmap

All identified flaws can be systematically mitigated **without changing any physical hardware** (<$60 BOM strictly preserved):

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   ACTIONABLE ZERO-HARDWARE-CHANGE FIX IMPLEMENTATION PLAN              │
├────┬─────────────────────────────┬──────────────────────────────┬─────────────────────┤
│ #  │ Identified Flaw / Gap       │ Concrete Code Remedy         │ Target File         │
├────┼─────────────────────────────┼──────────────────────────────┼─────────────────────┤
│ 1  │ Class-Agnostic Distance     │ Add Class-Specific Height &  │ ObstacleClassifier  │
│    │ Heuristic (0.8 / h)         │ Prior Table (H_real)         │ .kt                 │
├────┼─────────────────────────────┼──────────────────────────────┼─────────────────────┤
│ 2  │ Traffic Light Color         │ Crop bbox and run HSV color  │ ObstacleClassifier  │
│    │ Blindness                   │ centroid ratio (Red/Green)   │ .kt                 │
├────┼─────────────────────────────┼──────────────────────────────┼─────────────────────┤
│ 3  │ Rebound Fall False Alarms   │ Require 1.5s continuous low  │ FallDetector.kt     │
│    │                             │ variance stillness (sigma)   │                     │
├────┼─────────────────────────────┼──────────────────────────────┼─────────────────────┤
│ 4  │ Wi-Fi SoftAP Cuts 4G Data   │ Bind WebRTC to Cellular via  │ DrishtiService.kt / │
│    │                             │ NetworkCapabilities          │ LiveKitClient.kt    │
├────┼─────────────────────────────┼──────────────────────────────┼─────────────────────┤
│ 5  │ Hardcoded LiveKit Secret    │ Purge secret from APK; rely  │ LiveKitClient.kt    │
│    │                             │ 100% on Token Server dispatch│                     │
├────┼─────────────────────────────┼──────────────────────────────┼─────────────────────┤
│ 6  │ Mock Navigation Routes      │ Hook OSRM / Google Routes API│ drishti_agent.py    │
│    │                             │ in NavigationService         │                     │
├────┼─────────────────────────────┼──────────────────────────────┼─────────────────────┤
│ 7  │ 3D Spatial Audio Absence    │ Implement HRTF stereo audio  │ LocalTTS.kt /       │
│    │                             │ panner for direction beeps   │ AudioPanner.kt      │
└────┴─────────────────────────────┴──────────────────────────────┴─────────────────────┘
```