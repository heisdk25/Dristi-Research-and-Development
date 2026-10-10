# Paper Memory: AI-Based Wearable Vision Assistance System Using Large Vision-Language Models

## 1. Bibliographic & Metadata Information
* **Title:** AI-based wearable vision assistance system for the visually impaired: Integrating real-time object recognition and contextual understanding using large vision-language models
* **Authors:** Mirza Samad Ahmed Baig, Syeda Anshrah Gillani, Shahid Munir Shah, Mahmoud Aljawarneh, Abdul Akbar Khan, Muhammad Hamzah Siddiqui
* **Affiliations:** 
  * Department of Computing, Hamdard University, Karachi, Pakistan
  * Danat Fz LLC (Argaam), Karachi, Pakistan / Riyadh, Saudi Arabia
  * Doaz, South Korea
  * Faculty of Computing and Engineering Sciences, SZABIST University, Pakistan
  * Department of Cybersecurity and Cloud Computing, Applied Science Private University, Amman, Jordan
* **Journal / Venue:** *Telematics and Informatics Reports* (Elsevier / ScienceDirect), 2024–2026
* **Source PDF File:** [1-s2.0-S2772503026000447-main.pdf](file:///E:/HAckbios-R&D/1-s2.0-S2772503026000447-main.pdf) (16 pages, ~4.6 MB)

---

## 2. Abstract & Research Problem
Traditional computer vision wearables (e.g. Seeing AI, OrCam) provide rigid, template-driven audio classification ("dog 90%", "chair ahead") but cannot describe complex spatial relationships, answer conversational questions about unstructured scenes, or allow users to personalize the system with new friends and personal objects without cloud retraining.

Baig et al. propose a **wearable smart hat system** that bridges lightweight on-device vision with cloud **Large Vision-Language Models (LVLMs)**. The system offers three operational paradigms:
1. **Continuous On-Device Detection:** Detects nearby obstacles and familiar people using lightweight models running on a Raspberry Pi 4B.
2. **One-Click Voice-Driven Personalization:** A green button triggers voice recording to add a new person or object directly to a local SQLite embedding database without model fine-tuning.
3. **Conversational Scene Reasoning:** A blue button captures a high-resolution snapshot and queries a cloud LVLM to produce rich, contextual descriptions ("A crowded cafeteria with an open table to your left and a waiter carrying a tray").

---

## 3. Hardware Architecture & System Topology

```
+-------------------------------------------------------------------------------+
|                            WEARABLE HAT ENCLOSURE                             |
|  * 5MP USB CMOS Camera (Wide-Angle, Hat-Mounted facing line of sight)         |
|  * Dual Tactile Tact Switches (Green Button: Learn | Blue Button: LVLM Query) |
|  * USB Microphone + Earphone Jack (Audio Input & Output)                      |
+---------------------------------------------------|---------------------------+
                                                    | Ribbon Cable / USB
                                                    v
+-------------------------------------------------------------------------------+
|              EDGE PROCESSING UNIT: RASPBERRY PI 4 MODEL B (4GB RAM)            |
|  * Local Vision Engine: MobileNetV2-SSD (Nearby Object Detection)             |
|  * Face Recognition Engine: FaceNet (128-D Euclidean Face Embeddings)          |
|  * Personalization DB: Local SQLite (stores voice tags + 128D vectors)        |
|  * Local Speech Synthesis: Festival TTS (Offline Verbal Feedback)             |
+---------------------------------------------------|---------------------------+
                                                    | Wi-Fi / 4G Cellular Hotspot
                                                    v
+-------------------------------------------------------------------------------+
|                      CLOUD LVLM GENERATIVE REASONING LAYER                    |
|  * Cloud Vision-Language Model (OpenAI GPT-4V / Gemini Vision API)            |
|  * Contextual Prompting Pipeline: Natural language scene interpretation        |
|  * Response Streaming back to Raspberry Pi for Festival/eSpeak playback       |
+-------------------------------------------------------------------------------+
```

---

## 4. Algorithmic Pipeline & Mathematical Formulations

### 4.1 Tri-Modal Operational State Machine
* **Default Mode (No Button Pressed):** Runs MobileNetV2-SSD continuously on captured frames. Filters detections by depth/proximity (ignores distant background objects). If bounding box centroid and area indicate immediate proximity, checks if object/face is in the local SQLite database and verbalizes label via Festival TTS.
* **Green Button Mode (Personalized Registration):**
  1. Captures target cropped bounding box.
  2. Computes FaceNet 128-dimensional embedding vector $\mathbf{v}_{\text{new}} \in \mathbb{R}^{128}$.
  3. Prompts user through voice: *"Please say the name of this person or object."*
  4. Records audio tag, performs local speech-to-text, and writes `(label, vector, timestamp)` into SQLite.
  5. Subsequent inference performs nearest-neighbor Euclidean distance matching:
     $$D(\mathbf{v}, \mathbf{v}_i) = \sqrt{\sum_{k=1}^{128} (v_k - v_{i,k})^2}$$
     If $\min_i D(\mathbf{v}, \mathbf{v}_i) < \tau_{\text{match}}$, the system verbalizes the personalized name.
* **Blue Button Mode (Deep LVLM Contextual Query):**
  1. Captures full uncropped frame.
  2. Dispatches image to cloud LVLM with assistive accessibility prompt template.
  3. LVLM generates a descriptive situational summary which is spoken to the user.

---

## 5. Experimental Results & Performance Benchmarks

### 5.1 Recognition Performance by Lighting (Table 4)
| Lighting Condition | Precision | Recall | F1-Score | Overall Accuracy |
|---|---|---|---|---|
| **Good Lighting (Daylight / Office)** | **0.88** | **0.92** | **0.90** | **90.0%** |
| **Low Lighting (<50 lux)** | **0.76** | **0.74** | **0.75** | **80.0%** |

### 5.2 Performance Across Object Categories (Table 5)
* **Navigation Obstacles (Trip hazards, bollards, poles):** $\text{F1} = \mathbf{0.93}$
* **Food & Packaged Goods:** $\text{F1} = \mathbf{0.93}$
* **People & Faces (Known / Personalized):** $\text{F1} = \mathbf{0.91}$
* **Furniture (Chairs, Tables, Desks):** $\text{F1} = \mathbf{0.86}$ (degraded by shape ambiguity and occlusions)

### 5.3 User Study Evaluation (Table 6)
Tested on visually impaired participants across two cohorts:
* **Low-Vision Users:** Ease of use: $91\%$, User satisfaction: $4.4 / 5.0$, Object accuracy: $91.2\%$.
* **Totally Blind Users:** Ease of use: $79\%$, User satisfaction: $4.0 / 5.0$, Object accuracy: $88.7\%$.

---

## 6. Critical Bottlenecks & Weaknesses
1. **Turn-Based Button Latency:** Using physical buttons and turn-based cloud REST calls introduces multi-second delays ($>3-5\text{ s}$ per query), making it unsuitable for continuous fast walking.
2. **Thermal & Battery Footprint on Raspberry Pi 4:** Continuous MobileNetV2-SSD and camera capture consumes $>6-8\text{ W}$, resulting in high thermal dissipation on the user's hat and battery drain in $<2.5\text{ hours}$.
3. **No Dynamic Trajectory / Fall Detection:** The system lacks inertial sensors (IMU) for fall detection and cannot calculate time-to-collision (TTC).

---

## 7. Strategic Synthesis for Project Drishti
* **Validation of Hybrid AI:** Strongly corroborates Project Drishti's thesis that neither pure local vision nor pure cloud AI is sufficient—effective assistive technology requires combining fast local vision with cloud MLLM reasoning.
* **Personalized SQLite Feature Idea:** The one-shot voice-labeling registration mechanism (FaceNet embedding + SQLite) is an outstanding, privacy-preserving feature that can be implemented completely on-device in Drishti without cloud privacy violations.
