# Paper Memory: Bharat-Assist: Embedded Vision System Using Edge Computing & IoT

## 1. Bibliographic & Metadata Information
* **Title:** An Intelligent Embedded Vision System for Assisting Visually Impaired Users Using Edge Computing and IoT ("Bharat-Assist")
* **Authors:** Suraj Fulchand Chawan, Tejas Sudhakar Gulhane, Siddhant Shripal Mundre, Subodh Devidas Pal, Prof. D. G. Ingale
* **Affiliation:** Department of Computer Science and Engineering, Dr. Rajendra Gode Institute of Technology and Research, Amravati, Maharashtra, India
* **Journal / Venue:** *International Journal of Creative Research Thoughts (IJCRT)*, Vol. 14, Issue 4, April 2026; ISSN: 2320-2882
* **Source PDF File:** [IJCRT26A4047.pdf](file:///E:/HAckbios-R&D/IJCRT26A4047.pdf) (10 pages, ~555 KB)

---

## 2. Abstract & Research Problem
Urban pedestrian infrastructure in India presents severe chaotic challenges for visually impaired people: unpaved pathways, open manholes, stray animals (cows, dogs), uneven road edges, and erratic traffic (autorickshaws, two-wheelers). Cloud-based visual solutions fail frequently in India due to unpredictable 4G/cellular bandwidth, spotty coverage, and transmission latency exceeding 6 seconds.

Chawan et al. propose **"Bharat-Assist"**, an ultra-low-cost, self-contained embedded wearable vision aid built specifically around the **ESP32-CAM microcontroller** ($<\$10$ BOM). The system runs **TensorFlow Lite for Microcontrollers (TFLM)** with a quantized **SSD-MobileNet** model completely offline on the ESP32-CAM's Xtensa dual-core processor, supplemented by an ultrasonic safety-override sensor and bone-conduction Bluetooth audio.

---

## 3. Hardware Architecture & System Topology

```
+-------------------------------------------------------------------------------+
|                       BHARAT-ASSIST WEARABLE HEADFRAME                        |
|  * OV2640 2MP Camera Sensor (120° Wide-Angle Lens, Front-Facing)              |
|  * HC-SR04 Ultrasonic Sensor (Ranging 2 cm to 400 cm Proximity Safety Gate)   |
|  * NEO-6M GPS Module (Connected via hardware UART for SOS Geo-Tracking)       |
|  * 18650 Li-ion Cell with Step-Up DC-DC Boost Converter (3.7V -> 5V)           |
+---------------------------------------------------|---------------------------+
                                                    | On-Chip Bus
                                                    v
+-------------------------------------------------------------------------------+
|                 EDGE COMPUTING CORE: ESPRESSIF ESP32-CAM                      |
|  * Xtensa Dual-Core 32-bit LX6 Microprocessor @ 240 MHz                       |
|  * 520 KB Internal SRAM + 4 MB External PSRAM                                 |
|  * FreeRTOS Real-Time Operating System: Multitasking Priority Engine          |
|  * Inference Engine: TensorFlow Lite for Microcontrollers (TFLM)             |
+---------------------------------------------------|---------------------------+
                                                    | Bluetooth A2DP & GPIO
                                                    v
+-------------------------------------------------------------------------------+
|                       SENSORY OUTPUT & ESCALATION                             |
|  * Open-Ear Bone Conduction Headphones (Spoken Obstacle & Direction Alerts)   |
|  * Haptic Mini-Vibration Discs (Proximity Warning Pulses)                     |
|  * Wi-Fi / MQTT Telemetry & SMS Fallback Gateway                              |
+-------------------------------------------------------------------------------+
```

---

## 4. FreeRTOS Multitasking Software Pipeline

The firmware runs 4 asynchronous preemptive tasks on FreeRTOS:
1. **Vision Task (Core 1):**
   * Grabs JPEG frame from OV2640 DMA buffer in PSRAM.
   * Decompresses JPEG directly to RGB565 matrix.
   * Downsamples / bilinearly resizes image to $96 \times 96 \times 3$ pixels.
   * Runs quantized INT8 SSD-MobileNet inference via TFLM.
   * Applies confidence threshold ($\ge 60\%$) and outputs object class + spatial sector (Left, Center, Right).
2. **Sensor Task (Core 0):**
   * Continuously polls HC-SR04 ultrasonic echo pulses at $20\text{ Hz}$.
   * Reads NMEA GPS strings from the NEO-6M UART.
3. **Command / Priority Arbiter Task:**
   * **Safety Preemption Rule:** If ultrasonic distance $d < 50\text{ cm}$, the system **immediately overrides** the vision pipeline, emits a sharp haptic vibration burst, and sends an urgent vocal command (*"STOP!"*).
4. **Communication Task:**
   * Routes synthetic voice alerts via Bluetooth A2DP profile and transmits periodic MQTT telemetry when connected.

---

## 5. Experimental Results & Performance Benchmarks

### 5.1 Object Detection Accuracy on Indian Street Classes
Evaluated on custom datasets of Indian urban scenes:
* **Pedestrians / Persons:** **$92.4\%$** (confidence threshold $0.60$)
* **Furniture (Chairs, Tables, Stalls):** **$90.1\%$** (confidence threshold $0.65$)
* **Vehicles (Cars, Auto-rickshaws, Bikes):** **$88.7\%$** (confidence threshold $0.55$)
* **Stray Animals (Cows, Dogs):** **$84.3\%$** (confidence threshold $0.50$)
* **Overall Edge Accuracy:** **$91.1\%$**

### 5.2 Latency Benchmark: Localized ESP32 Edge vs. Cloud Processing
| Performance Metric | Localized Edge Processing (ESP32) | Cloud-Only Processing (4G) | Improvement |
|---|---|---|---|
| **Average Full Loop Time** | **860 ms** | **6,862 ms** | **87.5% Latency Reduction** |
| **Transmission Delay** | **17 ms** | **449 ms – 6,265 ms** | **99.6% Reduction** |
| **Network Dependency** | **Zero (100% Offline)** | Mandatory Continuous 4G | Immune to cell blackouts |
| **Data Bandwidth Load** | Negligible (Telemetry Only) | High (Continuous Raw Images) | Eliminates cellular data cost |

---

## 6. Critical Weaknesses & Bottlenecks
1. **Low Input Resolution ($96 \times 96$):** To fit model memory within the ESP32's 4MB PSRAM, images are downsampled to $96\times 96$, losing fine-grained details (cannot read text, currency, or distant street signs).
2. **860 ms Loop Speed Limit:** While far better than cloud ($6.8\text{ s}$), $860\text{ ms}$ ($\approx 1.16\text{ FPS}$) remains slightly slow for fast-moving hazards (e.g., oncoming motorbikes at $30\text{ km/h}$).
3. **No Conversational Reasoning:** The ESP32 is strictly an embedded microcontroller and cannot run or query Large Language Models.

---

## 7. Strategic Synthesis for Project Drishti
* **Validates ESP32-CAM Hardware Choice:** Proves that the $6 ESP32-CAM board is robust, inexpensive, and viable in harsh developing world environments.
* **Architecture Harmony with Drishti:** While Bharat-Assist attempts to force the entire deep learning model into the ESP32's tiny PSRAM ($96\times 96$ downsampling), **Project Drishti uses the ESP32-CAM strictly as an MJPEG streaming capture node**, streaming VGA ($640\times 480$) to the smartphone SoC, where YOLOv8n executes in **$26.4\text{ ms}$** (>28 FPS) with far higher accuracy!
