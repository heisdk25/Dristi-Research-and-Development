# Paper Memory: Sound-Based Navigation System for Visually Impaired Individuals

## 1. Bibliographic & Metadata Information
* **Title:** Sound-based navigation system for visually impaired individuals
* **Authors:** Emad Malaekah, Othman Alfahad, Mohsen Bakouri, Adel Gadallah, Suvad Selman, Ahmed Al Rashdi, Husham Saied
* **Affiliations:** 
  * Department of Biomedical Technology, Prince Sultan Military College of Health Sciences, Saudi Arabia
  * King Salman Center for Disability Research, Riyadh, Saudi Arabia
  * Department of Medical Equipment Technology, Majmaah University, Saudi Arabia
* **Journal / Venue:** *Journal of King Saud University – Engineering Sciences* (Elsevier / ScienceDirect), 2024–2026
* **Source PDF File:** [1-s2.0-S1687850726000038-main.pdf](file:///E:/HAckbios-R&D/1-s2.0-S1687850726000038-main.pdf) (13 pages, ~7.7 MB)

---

## 2. Abstract & Research Problem
Indoor navigation in complex buildings (hospitals, universities, administrative centers) remains an acute obstacle for visually impaired persons (VIPs). Standard GPS/GNSS fails indoors due to structural attenuation. Traditional white canes only detect obstacles in direct physical contact, while pure acoustic sensory substitution devices suffer from heavy cognitive load.

This paper proposes an **indoor robotic navigation system** combining:
1. **Arabic speech recognition** via Bluetooth headset to select destinations.
2. **Floor-embedded LED guidance strips** switched via relay matrices.
3. **An autonomous robot cart** equipped with Light-Dependent Resistor (LDR) optical sensors and an electromechanical flex-sensor compass.
4. **A rigid haptic handle** delivering 3-finger tactile motor feedback (thumb, middle, pinky) to steer the user along the path.

---

## 3. Hardware Architecture & System Topology

```
+-------------------------------------------------------------------------------+
|                             USER INTERACTION LAYER                            |
|  [Bluetooth Headset Mic] ----(Arabic Voice)----> [Speech Recognition Core]     |
|  [Haptic Steering Handle] <---(3x ERM Motors)---- [Arduino Microcontroller]   |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                           INDOOR INFRASTRUCTURE LAYER                         |
|  [BLE Beacons (Room 1 - Room 5)] ---> Local Indoor Localization Engine        |
|  [Floor LED Strip Light Matrix] <--- [Relay Control Matrix]                   |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                            AUTONOMOUS ROBOT CART                              |
|  * Optical Tracking: Array of LDR sensors + 50kΩ voltage dividers + N-MOSFETs  |
|  * Electromechanical Compass: Dual flex sensors detecting user-cart angular gap|
|  * Actuation: Dual DC gear motors with PWM speed controller (L298N driver)    |
|  * Power: 12V Li-ion battery pack with regulated power bus                     |
+-------------------------------------------------------------------------------+
```

### Key Hardware Components:
* **Optical Tracking Node:** LDR sensors positioned under the cart chassis facing the floor. Light threshold calibrated at $1.5\text{ lux}$ ($R_{\text{LDR}} \le 10\text{ k}\Omega$, MOSFET $V_{GS} \ge 2.5\text{ V}$ ON) versus dark ambient $< 1.0\text{ lux}$ ($R_{\text{LDR}} \ge 50\text{ k}\Omega$ OFF).
* **Electromechanical Compass:** Two resistive flex sensors embedded along the mechanical coupling between the user handle and cart chassis. Detects angular shearing when user fails to turn synchronously with the cart.
* **Haptic Tactile Handle:** 
  * *Middle finger motor:* Straight forward motion.
  * *Thumb motor:* Right turn alert.
  * *Pinky motor:* Left turn alert.
* **Controller:** Atmel ATmega328P / Arduino processing LDR differentials and driving H-bridge motors.

---

## 4. Algorithmic Workflow & Formulations

### 4.1 Speech Command Processing
* Trained on 5 Arabic keyword commands corresponding to 5 predefined destinations ("Room 1" to "Room 5").
* Successive sequential command architecture: each movement sequence locks until completion to avoid command queue overflow.
* Biometric acoustic feature verification isolates user voice from ambient chatter.

### 4.2 Light Tracking & Motor Actuation Logic
Percentage voltage error between observed and reference gate voltage:
$$\text{Percentage Error} = \frac{|V_{\text{observed}} - V_{\text{true}}|}{V_{\text{true}}} \times 100\%$$

### 4.3 Flex Sensor Angular Compass Error Calculation
When user walking angle $\theta_{\text{user}}$ diverges from robot trajectory $\theta_{\text{cart}}$:
$$\Delta R_{\text{flex}} = R_{\text{left}} - R_{\text{right}}$$
If $|\Delta R| > \text{Threshold}$, the microcontroller throttles the cart motor speed via PWM duty cycle reduction and pulses the respective directional vibration motor until $\Delta R \approx 0$.

---

## 5. Experimental Results & Performance Benchmarks

* **Voice Recognition Performance:**
  * Tested across 35 trained user samples and 32 untrained user samples.
  * **Accuracy:** $91.04\%$
  * **Precision:** $97.14\%$
  * **Sensitivity / Recall:** $87.18\%$
  * **F1-Score:** $91.89\%$
* **Path Tracking Accuracy:**
  * Tested on complex zig-zag floor routes over 3-minute continuous runs.
  * **Navigation Path Error:** $4.0\%$ (caused by ambient stray light noise and voltage fluctuations across LDR dividers).
* **Speed Regulation Error:**
  * **PWM Control Deviation:** $3.0\%$ electrical fluctuation under battery discharge.

---

## 6. Critical Weaknesses & Bottlenecks
1. **High Infrastructure Dependence:** Requires pre-installing dedicated LED light strips and relay switches under floors throughout the entire building. Completely inoperable in un-retrofitted or outdoor environments.
2. **Mechanical Cumbersomeness:** Requires the user to push/pull a physical motorized cart, hindering stair negotiation, narrow corridors, or rough terrain.
3. **No Vision or Semantic Understanding:** The system has zero awareness of obstacles on the floor (e.g., dropped bags, other people crossing the LED line). If an obstacle blocks the LED strip, the cart will either collide or stall.

---

## 7. Strategic Synthesis for Project Drishti
* **Contrasting Paradigm:** Malaekah et al. represent an **infrastructure-heavy mechanical approach**, whereas Project Drishti adopts an **infrastructure-free egocentric vision approach** (YOLOv8n + MLLMs).
* **Insight on Haptic Steering:** The 3-finger vibration handle (middle=straight, thumb=right, pinky=left) demonstrates an effective ergonomic alternative to audio feedback that leaves auditory canals clear.
