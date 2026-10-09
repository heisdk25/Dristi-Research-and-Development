# Paper Memory: DrishT: Dual-Stream Mobile Architecture for Real-Time Scene Understanding

## 1. Bibliographic & Metadata Information
* **Title:** DrishT: A Dual-Stream Mobile Architecture for Real-Time Scene Understanding in Assistive Navigation
* **Authors:** Daljeet Singh Lotey, Dr. Narayan Kulkarni
* **Affiliation:** Preprint (Under Review)
* **Date / Venue:** Posted January 14, 2026, DOI: 10.22541/au.176843166.60388360/v1
* **Source PDF File:** [au.176843166.60388360_v1.pdf](file:///E:/HAckbios-R&D/au.176843166.60388360_v1.pdf) (15 pages, ~420 KB)

---

## 2. Abstract & Research Problem
Existing assistive vision systems treat object detection and optical character recognition (OCR) in **isolated pipelines**. For instance, an object detector detects a generic "door" while an OCR engine detects the word "Exit", but neither system connects that the "Exit" text labels that specific door. This lack of spatial-semantic association leaves visually impaired users without actionable context.

Lotey and Kulkarni propose **DrishT**, a mobile-optimized dual-stream neural architecture running entirely on mid-range Android smartphones (Snapdragon 660+, devices $<\$200$). The system executes simultaneous object detection and scene text recognition, fusing both streams through a **spatial distance-weighted attention layer** to produce unified audio descriptions (*"Exit door 2 meters ahead"*).

---

## 3. Dual-Stream System Architecture

```
                      Input Frame (640 × 480 RGB)
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
[Stream 1: Object Detection]                     [Stream 2: Text Recognition]
  * Model: SSD-VGG16 (Input 300x300x3)             * Model: CRNN (Input 32xWx3)
  * 13 Conv Layers (conv1_1 to pool5)              * 5 Conv Layers + 2 BiLSTM Layers
  * 6 Multi-scale heads: 8,732 anchors             * Connectionist Temporal Classification
  * 82 Classes (COCO + door + stairs)              * Outputs character token sequences
         │                                                   │
         │ Bounding Boxes & Confidence                       │ Text Strings & Polygonal BBoxes
         └─────────────────────────┬─────────────────────────┘
                                   │
                                   v
             [SEMANTIC FUSION LAYER (Distance-Weighted Attention)]
               * Spatial Euclidean Distance Calculation
               * Intersection-over-Union (IoU) Scoring
               * Vertical Alignment & Aspect-Ratio Heuristics
               * Priority Weight Association Matrix
                                   │
                                   v
             [AUDIO SYNTHESIS ENGINE (Android Native TTS)]
               * Unified Audio Output: Object + Text Association
```

---

## 4. Mathematical Formulations & Model Specifications

### 4.1 SSD-VGG16 Multi-Task Loss Function
$$\mathcal{L}(x, c, l, g) = \frac{1}{N} \left[ \mathcal{L}_{\text{conf}}(x, c) + \alpha \cdot \mathcal{L}_{\text{loc}}(x, l, g) \right] \quad (\alpha = 1.0)$$

* **Localization Loss (Smooth L1 over offsets):**
  $$\mathcal{L}_{\text{loc}}(x, l, g) = \sum_{i \in \text{Pos}} \sum_{m \in \{cx, cy, w, h\}} x_{ij}^k \cdot \text{smooth}_{L1}(l_i^m - \hat{g}_j^m)$$
  where ground-truth offsets are normalized:
  $$\hat{g}_j^{cx} = \frac{g_j^{cx} - d_i^{cx}}{d_i^w}, \quad \hat{g}_j^{cy} = \frac{g_j^{cy} - d_i^{cy}}{d_i^h}, \quad \hat{g}_j^w = \log\left(\frac{g_j^w}{d_i^w}\right), \quad \hat{g}_j^h = \log\left(\frac{g_j^h}{d_i^h}\right)$$
* **Confidence Loss (Softmax Cross-Entropy with Hard Negative Mining 3:1):**
  $$\mathcal{L}_{\text{conf}}(x, c) = -\sum_{i \in \text{Pos}} x_{ij}^p \log(\hat{c}_i^p) - \sum_{i \in \text{Neg}} \log(\hat{c}_i^0)$$
* **Navigation-Specific Custom Anchors:** Modified aspect ratios tailored for navigation structures:
  * Doors (tall/narrow): aspect ratio $1:3$
  * Signs (wide/horizontal): aspect ratio $3:1$
  * Modified scales: $[0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.05]$

### 4.2 CRNN Text Recognition Stream
* **Feature Extractor:** 5 convolutional layers reducing height from 32 to 1 while preserving horizontal token width $W/4$.
* **Sequence Modeling:** 2 bidirectional LSTM layers (256 hidden units each, 512 bidirectional output).
* **Transcription:** CTC Loss decoding across 63 character classes (alphanumeric + blank token).

### 4.3 Semantic Spatial-Textual Fusion Layer
Associates text box $T_j$ with candidate object bounding box $O_i$ using a composite spatial cost metric:
$$S(O_i, T_j) = w_1 \cdot \text{IoU}(O_i, T_j) + w_2 \cdot \exp\left(-\frac{\|\mathbf{c}_{O_i} - \mathbf{c}_{T_j}\|_2^2}{2\sigma^2}\right) + w_3 \cdot \text{Align}(O_i, T_j)$$
Achieves **$84.3\%$ association accuracy** in matching embedded text to the correct object container.

---

## 5. Mobile Optimization & Performance Benchmarks

### 5.1 Quantization & Footprint (TFLite INT8)
* **Combined FP32 Size:** $60.4\text{ MB}$ $\to$ **INT8 Size:** **$14.5\text{ MB}$** (**$76\%$ reduction**).
* **mAP Degradation:** Only $1.8\%$ drop ($43.0\%$ FP32 $\to$ $41.2\%$ INT8).
* **End-to-End Latency:** **$182\text{ ms}$** on Snapdragon 660+ processor.

### 5.2 Accuracy Metrics
* **Object Detection:** $41.2\%\text{ mAP}_{50}$ (trained on 10,000+ navigation scenes with specialized door/stairs/sign classes).
* **Scene Text Recognition:** $91.5\%$ word-level recognition accuracy ($92.0\%$ on restaurant menus).
* **Semantic Object-Text Association:** $84.3\%$ correct association.

---

## 6. Critical Weaknesses & Bottlenecks
1. **Legacy Backbone Architecture:** Uses VGG16 as the SSD backbone. While quantized to INT8, VGG16 has higher parameter redundancy and lower accuracy than modern YOLOv8 CSPDarknet backbones.
2. **No Conversational Reasoning:** The audio output is rule-based and template-driven. It cannot summarize complex documents or answer user questions about the scene.
3. **Absence of Fall Detection or Redundant Sensors:** Focuses purely on visual scene perception without IMU telemetry or emergency fall escalation.

---

## 7. Strategic Synthesis for Project Drishti
* **Critical Conceptual Alignment:** Lotey's "DrishT" paper explores the exact same challenge of fusing object detection with text recognition on mobile devices.
* **Key Algorithmic Contribution:** The **distance-weighted spatial fusion layer** ($S(O_i, T_j)$) is a valuable architectural technique that Project Drishti can adopt to link Google ML Kit OCR text tokens directly to YOLOv8n obstacle bounding boxes before dispatching context to the LiveKit cloud MLLM.
