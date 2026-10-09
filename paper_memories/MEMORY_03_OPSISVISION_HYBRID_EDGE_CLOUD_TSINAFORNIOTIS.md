# Paper Memory: OpsisVision: Multimodal AI Assistance with Hybrid Edge-Cloud Architecture

## 1. Bibliographic & Metadata Information
* **Title:** OpsisVision: A Multimodal AI Assistance System for the Blind and Visually Impaired with Hybrid Edge-Cloud Architecture
* **Author:** Grigorios Tsinaforniotis
* **Affiliation:** Protos AI Agency (Single Member Private Company), Greece
* **Date / Venue:** Preprint (December 29, 2025 / Posted January 8, 2026), DOI: 10.22541/au.176789702.20056088/v1
* **Source PDF File:** [au.176789702.20056088_v1.pdf](file:///E:/HAckbios-R&D/au.176789702.20056088_v1.pdf) (18 pages, ~376 KB)

---

## 2. Abstract & Research Problem
Commercial assistive smart glasses like OrCam MyEye ($6,000) or Envision Glasses ($3,500) are cost-prohibitive for over 90% of visually impaired people globally. Furthermore, existing mobile apps rely completely on cloud servers (Be My Eyes), creating dangerous failures in network dead zones, or rely on simplistic rule-based audio prompts without conversational depth.

OpsisVision introduces an **open, low-cost multimodal AI assistance wearable** featuring:
1. **A 3D-printed glasses frame** housing stereoscopic 4K dual cameras.
2. **Local edge AI processing on NVIDIA Jetson Orin** running **YOLOv11** object detection and **StereoBM disparity depth estimation**.
3. **Voice-first Greek natural interaction** powered by local **Vosk** wake-word detection and cloud **Whisper STT**.
4. **Cloud Multimodal LLM reasoning** via **GPT-4o** for high-level semantic scene comprehension.
5. **Open-ear bone conduction audio** to prevent ear canal acoustic occlusion.

---

## 3. Hardware Architecture & BOM Cost Breakdown

```
+-------------------------------------------------------------------------------+
|                    3D-PRINTED PLA SMART GLASSES FRAME                         |
|  * 2x 4K USB Webcams (Stereoscopic pair, 6 cm baseline separation)            |
|  * Directional USB Microphone (Captures Greek voice utterances)              |
|  * Bone Conduction Headphones (Transmits audio via skull bone vibration)      |
+---------------------------------------------------|---------------------------+
                                                    | USB-C Cables
                                                    v
+-------------------------------------------------------------------------------+
|                      COMPUTE UNIT: NVIDIA JETSON ORIN NANO                    |
|  * Tier Option A (Cloud-Hybrid): Jetson Orin 8GB (~€250)                      |
|  * Tier Option B (Local Offline): Jetson Orin 16GB / 64GB (~€1,000 - €2,000)  |
|  * 45W USB-C PD Anker Powerbank (Mobile battery supply)                      |
|  * Total System BOM Cost: ~€470 (8GB version) to ~€2,220 (64GB offline)       |
+-------------------------------------------------------------------------------+
```

### Commercial Hardware Cost Comparison:
* **OrCam MyEye Pro:** $\approx \$6,000$ (Proprietary, zero cloud dialogue, rigid OCR)
* **Envision Glasses:** $\approx \$3,500$ (Google Glass EE2 hardware, $<2\text{ hr}$ battery)
* **OpsisVision (Hybrid 8GB):** $\mathbf{\approx €470}$ (Open architecture, stereoscopic depth, GPT-4o conversational reasoning)

---

## 4. Algorithmic Pipeline & Software Flow

```
[Continuous Mic Audio] 
         │
         ▼
[Step 1: Local Wake-Word Detection (Vosk)]
   - Listens offline for Greek wake-word: "γυαλιά" (glasses)
   - Zero cloud data transmission during idle standby (Privacy & Power Saving)
         │ Wake-Word Detected
         ├──────────────────────────────────────────┐
         ▼                                          ▼
[Step 2: Cloud Voice Processing]           [Step 3 & 4: Local Vision & Depth]
  - Records 5s audio buffer                  - 4K stereo camera frame capture
  - Dispatches to OpenAI Whisper API         - Left frame -> Local YOLOv11 detection
  - Returns Greek text transcript            - StereoBM disparity depth calculation
         │                                          │
         └────────────────────┬─────────────────────┘
                              │ Prompt: [Transcript + Stereo Crop + YOLO Detections]
                              ▼
           [Step 5: Cloud Multimodal Reasoning (GPT-4o)]
             - Scene semantic interpretation
             - Navigation corridor evaluation & Q&A
                              │
                              ▼
           [Step 6: Text-to-Speech & Output]
             - Synthesized Greek voice sent to Bone Conduction Headphones
```

### Depth Formulation via StereoBM:
Given dual cameras with baseline $B = 6.0\text{ cm}$ and focal length $f$:
$$\text{Depth } Z = \frac{f \cdot B}{d_{\text{disparity}}}$$
Calculated locally on the Jetson Orin in real time without cloud upload, ensuring that raw metric distance to obstacles is known immediately.

---

## 5. Privacy, Ethics, and Regulatory Compliance
* **EU GDPR Article 9:** Facial imagery and biometric data are treated as sensitive personal data. OpsisVision ensures zero passive streaming to the cloud: the cloud link is only engaged after explicit wake-word activation ("γυαλιά").
* **European Accessibility Act (EAA) 2025:** Provides an open, verifiable assistive system architecture compliant with upcoming EU digital accessibility standards.

---

## 6. Critical Weaknesses & Bottlenecks
1. **Physical Bulk & Heat:** Wearing dual 4K webcams on a 3D-printed glasses frame creates front-heavy torque on the nose bridge.
2. **Compute Module Portability:** A Jetson Orin Nano requires a dedicated carrying case/pouch and a heavy 45W Power Delivery powerbank.
3. **Turn-Based Wake-Word Overhead:** Relying on a 5-second audio record-and-send cycle creates a $>4-6\text{ second}$ total round-trip turn time, failing to provide immediate sub-second collision reflexes.

---

## 7. Strategic Synthesis for Project Drishti
* **Model Evolution:** OpsisVision is one of the earliest academic assistive works adopting **YOLOv11** alongside **GPT-4o**.
* **Contrast with Drishti:** While OpsisVision runs on a high-power Jetson Orin with stereo cameras (~€470), **Drishti achieves sub-400ms obstacle reflexes on a commodity smartphone + $6 ESP32-CAM**, lowering the financial barrier by another order of magnitude.
