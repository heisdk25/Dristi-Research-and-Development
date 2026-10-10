# Master Research Compendium: Assistive Vision, Edge AI, and Wearable Mobility Systems

> **Corpus Location:** `E:\HAckbios-R&D\paper_memories\`  
> **Total Analyzed Literature:** 8 Landmark Research Papers + Foundational Drishti Manuscript `a (1).pdf`  
> **Date Compiled:** October 2026

---

## 1. Literature Repository Navigation & Direct Links

| # | Document Memory File | Original Manuscript File | Key Innovation / Focus |
|---|---|---|---|
| **01** | [MEMORY_01_SOUND_BASED_NAVIGATION_MALAEKAH.md](file:///E:/HAckbios-R&D/paper_memories/MEMORY_01_SOUND_BASED_NAVIGATION_MALAEKAH.md) | [1-s2.0-S1687850726000038-main.pdf](file:///E:/HAckbios-R&D/papers/1-s2.0-S1687850726000038-main.pdf) | Indoor autonomous robot cart guided by floor LED strips, Arabic voice commands, and 3-finger haptic handle. |
| **02** | [MEMORY_02_LVLM_WEARABLE_VISION_ASSIST_BAIG.md](file:///E:/HAckbios-R&D/paper_memories/MEMORY_02_LVLM_WEARABLE_VISION_ASSIST_BAIG.md) | [1-s2.0-S2772503026000447-main.pdf](file:///E:/HAckbios-R&D/papers/1-s2.0-S2772503026000447-main.pdf) | Wearable smart hat (Raspberry Pi 4B + MobileNetV2-SSD + FaceNet) with one-click voice personalization in local SQLite and cloud LVLM scene reasoning. |
| **03** | [MEMORY_03_OPSISVISION_HYBRID_EDGE_CLOUD_TSINAFORNIOTIS.md](file:///E:/HAckbios-R&D/paper_memories/MEMORY_03_OPSISVISION_HYBRID_EDGE_CLOUD_TSINAFORNIOTIS.md) | [au.176789702.20056088_v1.pdf](file:///E:/HAckbios-R&D/papers/au.176789702.20056088_v1.pdf) | 3D-printed smart glasses with dual 4K stereo cameras on NVIDIA Jetson Orin running YOLOv11 + StereoBM depth, Vosk Greek wake-word, and cloud GPT-4o. |
| **04** | [MEMORY_04_DRISHT_DUAL_STREAM_MOBILE_LOTEY.md](file:///E:/HAckbios-R&D/paper_memories/MEMORY_04_DRISHT_DUAL_STREAM_MOBILE_LOTEY.md) | [au.176843166.60388360_v1.pdf](file:///E:/HAckbios-R&D/papers/au.176843166.60388360_v1.pdf) | Mobile dual-stream architecture (SSD-VGG16 + CRNN) with distance-weighted attention layer associating detected objects with embedded text labels (14.5MB INT8, 182ms). |
| **05** | [MEMORY_05_EDGE_CLOUD_INTELLIGENT_CANE_MA.md](file:///E:/HAckbios-R&D/paper_memories/MEMORY_05_EDGE_CLOUD_INTELLIGENT_CANE_MA.md) | [electronics-11-02266.pdf](file:///E:/HAckbios-R&D/papers/electronics-11-02266.pdf) | Three-tier IoT white cane (Arduino + Raspberry Pi + Cloud GPU) combining ultrasonic aerial hazard detection, MPU6050 fall detection, and cloud traffic light recognition. |
| **06** | [MEMORY_06_BHARAT_ASSIST_EMBEDDED_VISION_CHAWAN.md](file:///E:/HAckbios-R&D/paper_memories/MEMORY_06_BHARAT_ASSIST_EMBEDDED_VISION_CHAWAN.md) | [IJCRT26A4047.pdf](file:///E:/HAckbios-R&D/papers/IJCRT26A4047.pdf) | "Bharat-Assist" ultra-low-cost edge system on ESP32-CAM ($<\$10$) running TFLM quantized SSD-MobileNet with HC-SR04 ultrasonic safety override for Indian street navigation. |
| **07** | [MEMORY_07_LOW_COST_MULTIFUNCTIONAL_GLASSES_KRAL.md](file:///E:/HAckbios-R&D/paper_memories/MEMORY_07_LOW_COST_MULTIFUNCTIONAL_GLASSES_KRAL.md) | [Low-Cost_Multifunctional_Assistive_Device_for_Visually_Impaired_Individuals.pdf](file:///E:/HAckbios-R&D/papers/Low-Cost_Multifunctional_Assistive_Device_for_Visually_Impaired_Individuals.pdf) | Wearable smart glasses (Raspberry Pi Zero 2W + Arducam IMX519 16MP autofocus) with OCR reading, CNN scene descriptions, and remote sighted volunteer assistance. |
| **08** | [MEMORY_08_SEMANTIC_VISUAL_SLAM_WEARABLE_CHEN.md](file:///E:/HAckbios-R&D/paper_memories/MEMORY_08_SEMANTIC_VISUAL_SLAM_WEARABLE_CHEN.md) | [sensors-21-01536-v2.pdf](file:///E:/HAckbios-R&D/papers/sensors-21-01536-v2.pdf) | Wearable navigation device with Intel RealSense RGB-D camera and NVIDIA Jetson running modified ORB-SLAM2 and CNN semantic segmentation for 3D room mapping (~5cm accuracy). |
| **CORE** | [DRISHTI_SYSTEM_MEMORY.md](file:///E:/HAckbios-R&D/DRISHTI_SYSTEM_MEMORY.md) | [a (1).pdf](file:///E:/HAckbios-R&D/papers/a%20(1).pdf) | Foundational literature review & system blueprint for Project Drishti (Sub-400ms YOLOv8n INT8 edge reflex + LiveKit WebRTC GPT-4o conversational intelligence + fall dispatch). |

---

## 2. Multi-Dimensional Comparative Literature Matrix

| System / Paper | Hardware Form Factor | Processing Architecture | Vision & Sensor Suite | Interaction Mode | Latency Hierarchy | BOM Cost Range |
|---|---|---|---|---|---|---|
| **Malaekah et al. [01]** | Wheeled Robot Cart + Rigid Handle | Arduino / ATmega328P | LDR optical array, flex sensors, BLE | Arabic Voice + 3-Motor Haptic Handle | Local reflex (~4% error) | $\approx \$80 - \$120$ |
| **Baig et al. [02]** | Smart Hat Wearable | Raspberry Pi 4B (4GB) | 5MP USB Camera | 2 Tactile Buttons + Voice SQLite + Cloud LVLM | On-Device MobileNet + Cloud LVLM (3–5s) | $\approx \$110 - \$140$ |
| **OpsisVision [03]** | 3D-Printed Eyewear | NVIDIA Jetson Orin Nano (8GB–64GB) | Dual 4K USB Cams (Stereo 6cm baseline) | Greek Vosk wake-word + Whisper + Bone Conduction | Local YOLOv11 + Cloud GPT-4o (4–6s) | $\approx €470 - €2,220$ |
| **DrishT [04]** | Android Smartphone | Qualcomm Snapdragon 660+ SoC | Single Smartphone RGB Camera | Text-to-Speech Audio | Dual-Stream TFLite INT8 (182 ms end-to-end) | Commercial Phone ($<\$200$) |
| **Ma et al. [05]** | Intelligent White Cane | Arduino + Raspberry Pi + Cloud GPU | Ultrasonic array, MPU6050 IMU, GPS, USB Cam | Voice synthesis + Bluetooth earphone + Buzzer | Split: Local Ultrasonic ($<50\text{ms}$) + Cloud CV (1.8–3.2s) | $\approx \$130 - \$180$ |
| **Bharat-Assist [06]** | Wearable Headframe | Espressif ESP32-CAM (Xtensa LX6) | OV2640 2MP camera, HC-SR04, NEO-6M GPS | Bone Conduction + Haptic Discs | 100% Offline Edge (860 ms loop) | $\mathbf{<\$10 - \$15}$ |
| **Král et al. [07]** | Smart Glasses | Raspberry Pi Zero 2W (512MB RAM) | Arducam IMX519 16MP Autofocus Camera | 4 Tactile Frame Buttons + TTS + Volunteer Call | Local OCR/CNN + WebRTC Volunteer Stream | $\approx \$80 - \$100$ |
| **Chen et al. [08]** | Wearable Chest/Head Unit | NVIDIA Jetson Embedded GPU | Intel RealSense RGB-D (Stereo IR + Color) | IFLYTEK Speech Synthesis + BT Earphones | Real-Time SLAM ($\ge 30\text{ FPS}$, ~5cm error) | $\approx \$600 - \$1,000$ |
| **Project Drishti [CORE]** | Smart Sunglasses + Phone | ESP32-CAM + Android Mobile SoC + Cloud | Dual Camera (ESP32 MJPEG + CameraX Fallback) + 3-Axis IMU | Hands-Free Voice + Priority Ducking + Silero VAD | **Tier 1: <400ms reflex (26.4ms infer) / Tier 2: 1.1–2.2s MLLM** | **$<\$15$ Sunglasses Add-on** |

---

## 3. Cross-Cutting Engineering Insights

### 3.1 Ergonomics: Cane vs. Monolithic Eyewear vs. Decoupled Smart Sunglasses
* **Cane Mounts (Ma et al. [05]):** Suffers from continuous $>2\text{ Hz}$ cyclical sweeping oscillations, causing severe rolling-shutter tearing and motion blur that degrades deep learning inference.
* **Monolithic Eyewear Mounts (Tsinaforniotis [03], Král et al. [07]):** Natural head-gaze alignment, but suffers from heavy processors on the nasal bridge, thermal dissipation near the temples, and battery life limited to $<2\text{ hours}$.
* **Decoupled Smart Sunglasses (Drishti):** Emerges as the optimal physical compromise: camera and ESP32 transmitter embedded directly into lightweight sunglasses eyewear frames (<38g) with dark UV lenses (socially familiar and protective), offloading heavy compute and battery to the pocket Android smartphone via Wi-Fi SoftAP. Keeping hands completely free for white-cane ground sweeping.

### 3.2 Edge Computing vs. Cloud Trade-Offs
* **Pure Cloud (Be My Eyes, early prototypes):** Fatal flaw in assistive navigation—multi-second network latency ($3-7\text{ s}$) and complete system freeze during subway or rural cell dropouts.
* **Pure Microcontroller Edge (Bharat-Assist [06]):** Extreme low cost ($<\$10$), but downsamples images to $96\times 96$ due to 4MB PSRAM limits, losing ability to read text or small obstacles.
* **Dual-Tier Decoupled Architecture (Drishti, OpsisVision, Baig):** The definitive Generation-4 paradigm: **sub-400ms deterministic on-device safety reflex** for obstacles and falls, coupled with **cloud MLLMs** only for conversational scene reasoning.
