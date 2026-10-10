# Paper Memory: Low-Cost Multifunctional Assistive Device for Visually Impaired Individuals

## 1. Bibliographic & Metadata Information
* **Title:** Low-Cost Multifunctional Assistive Device for Visually Impaired Individuals
* **Authors:** Richard Král, Patrik Jacko, Tibor Vince
* **Affiliation:** Department of Theoretical and Industrial Electrical Engineering, Technical University of Košice, Košice, Slovakia
* **Journal / Venue:** *IEEE Access*, Vol. 13, pp. 56326–56337, March/April 2025; DOI: 10.1109/ACCESS.2025.3554366
* **Source PDF File:** [Low-Cost_Multifunctional_Assistive_Device_for_Visually_Impaired_Individuals.pdf](file:///E:/HAckbios-R&D/Low-Cost_Multifunctional_Assistive_Device_for_Visually_Impaired_Individuals.pdf) (12 pages, ~7.1 MB)

---

## 2. Abstract & Research Problem
Existing commercial smart glasses for the blind (e.g., Envision Glasses at $\approx \$3,500$, OrCam MyEye at $\approx \$4,500$) are prohibitively expensive and frequently lack flexible integration between automatic AI tools and human-in-the-loop remote assistance. Conversely, pure smartphone apps require manual aiming, occupying hands that must remain dedicated to sweeping a white cane.

Král et al. present a **low-cost, lightweight multifunctional smart glasses system** built around a **Raspberry Pi Zero 2W** and a motorized autofocus camera (**Arducam IMX519 16MP**). The system integrates:
1. **Real-time document and scene text OCR** with text-to-speech feedback.
2. **On-device CNN scene and obstacle description**.
3. **A 4-button tactile frame interface**.
4. **Cloud-based Remote Volunteer Assistance**, enabling live video streaming to sighted volunteers who assist in complex, ambiguous scenarios.
5. Extensive real-world clinical validation at the **Rehabilitation Center for the Visually Impaired in Levoča, Slovakia**.

---

## 3. Hardware Architecture & Specifications

```
+-------------------------------------------------------------------------------+
|                      WEARABLE SMART GLASSES FRAME                             |
|  * Arducam IMX519 16MP Camera (Motorized Autofocus, 80° FOV)                  |
|  * 4x Tactile Tact Switches (Navigation, OCR, Audio Record, Volunteer Call)   |
|  * External USB Sound Card + In-Ear Headphone Transducer                      |
|  * Custom 3D-Printed Lightweight Eyewear Mount (Ergonomic Weight Balance)     |
+---------------------------------------------------|---------------------------+
                                                    | CSI Ribbon Cable & USB
                                                    v
+-------------------------------------------------------------------------------+
|            COMPUTE PLATFORM: RASPBERRY PI ZERO 2W (16 GRAMS)                  |
|  * SoC: Broadcom BCM2710A1 Quad-Core 64-bit ARM Cortex-A53 @ 1.0 GHz         |
|  * RAM: 512 MB LPDDR2 SDRAM                                                   |
|  * Dimensions: 65 mm × 30 mm × 13 mm                                          |
|  * Connectivity: 2.4 GHz Wi-Fi 802.11b/g/n + Bluetooth 4.2 BLE               |
|  * Power Consumption: ~1.5W – 2.5W (5V Micro-USB Powerbank)                   |
+---------------------------------------------------|---------------------------+
                                                    | Wi-Fi / Hotspot WebRTC/RTMP
                                                    v
+-------------------------------------------------------------------------------+
|                    CLOUD REMOTE VOLUNTEER ASSISTANCE SERVER                   |
|  * Volunteer Dispatch Portal (WebRTC Live Video Stream + Two-Way Audio)       |
|  * Volunteer Chat-to-Speech Engine (Transcribes text notes to speech)         |
|  * AI Assistance Backend (Cloud Deep Learning Fallback)                       |
+-------------------------------------------------------------------------------+
```

---

## 4. Software Design & Five Operational Modes

1. **Text Reading Mode (OCR + TTS):**
   * Uses Arducam IMX519 motorized autofocus to capture needle-sharp macro photographs of documents, medication labels, or street signs.
   * Extracts text tokens using OCR and reads them aloud via TTS.
2. **AI Scene Description Mode:**
   * Executes CNN-based computer vision to identify surrounding objects, pedestrians, and obstacles, generating audio prompts.
3. **Audio File Playback Mode:**
   * Allows the user to navigate and listen to recorded voice notes, audiobooks, and stored audio messages.
4. **Voice Recording Mode:**
   * Rapid one-touch audio memo capture.
5. **Remote Volunteer Assistance Mode (Human-in-the-Loop):**
   * Connects to a cloud server, retrieves available online volunteers, and streams real-time forward video.
   * Volunteer views video on desktop/mobile browser and provides verbal and textual navigation guidance directly to the user's earpiece.

---

## 5. Clinical & Usability Evaluation (Rehabilitation Center in Levoča)

Evaluated with 5 visually impaired participants across real-world navigation and daily living tasks:
* **Text Reading Accuracy:** High OCR fidelity on printed paper documents, medicine packaging, and food labels due to the **motorized autofocus lens** (prevents blur common to fixed-focus micro-cameras).
* **Usability & Tactile Control:** All participants successfully operated the 4-button tactile layout without sight after a brief orientation session.
* **Remote Assistance Feedback:** Participants reported high emotional security and reduced anxiety in unfamiliar environments when having on-demand human volunteer support.
* **Cost Comparison:** Total prototype BOM cost is under **$100**, compared to $3,500+ commercial devices.

---

## 6. Critical Weaknesses & Bottlenecks
1. **Compute Throttling on 512MB RAM:** The Raspberry Pi Zero 2W's 512MB RAM severely restricts running large local deep learning models (such as modern YOLOv8 or vision transformers), causing local inference latency to exceed $1.5-3.0\text{ seconds}$.
2. **Thermal Dissipation Near Temple:** Continuous quad-core execution heats the Pi Zero 2W board, creating noticeable warmth along the glasses temple frame.
3. **No Autonomous Fall Detection:** The glasses frame lacks an IMU accelerometer/gyroscope for fall impact detection or emergency automated 911/caregiver escalation.

---

## 7. Strategic Synthesis for Project Drishti
* **Importance of Autofocus:** Král et al. prove that for OCR and text reading, a motorized autofocus camera (IMX519) significantly outperforms fixed-focus pinhole cameras (like the standard ESP32 OV2640).
* **Synergy with Drishti:** Project Drishti can incorporate Král et al.'s **Remote Sighted Volunteer fallback** concept alongside the cloud MLLM, providing a human-in-the-loop option for complex safety-critical tasks.
