# Drishti — Vultr Cloud Deployment Guide

This guide walks you through deploying the **Drishti Backend Architecture** (LiveKit Token Server + LiveKit Voice Agent Worker) on [Vultr](https://www.vultr.com/) using **Vultr Cloud Compute** and **Docker Compose**.

---

## 1. Architecture Overview on Vultr

```
┌─────────────────────────────────────────────────────────────┐
│                       Vultr Cloud                           │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                 Ubuntu 24.04 LTS                    │   │
│   │                                                     │   │
│   │  ┌─────────────────────────┐                        │   │
│   │  │   drishti-token-server  │ <── Port 8000 (HTTP)   │   │
│   │  │   (FastAPI / Uvicorn)   │                        │   │
│   │  └───────────┬─────────────┘                        │   │
│   │              │ JWT Sign                             │   │
│   │              ▼                                      │   │
│   │  ┌─────────────────────────┐                        │   │
│   │  │   drishti-livekit-agent │ ── Outbound WebSocket  │   │
│   │  │   (Python Agent Worker) │    (wss://...)         │   │
│   │  └─────────────────────────┘                        │   │
│   │                                                     │   │
│   │  ┌─────────────────────────┐ (Optional HTTPS)       │   │
│   │  │      drishti-caddy      │ <── Port 80 / 443      │   │
│   │  │   (Automated SSL TLS)   │                        │   │
│   │  └─────────────────────────┘                        │   │
│   └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │ Public IP / HTTPS
                           ▼
              ┌─────────────────────────┐
              │  Android Client Phone   │
              │   (4G / 5G / Wi-Fi)     │
              └─────────────────────────┘
```

The stack contains two primary microservices:
1. **Token Server (`token-server/`)**: FastAPI application exposing `GET /health` and `GET /token`. Mobile clients anywhere in the world fetch signed LiveKit access tokens from here.
2. **Agent Worker (`agent/`)**: 24/7 background Python process connected to LiveKit Cloud WebRTC rooms, performing low-latency speech recognition, Gemini/Groq LLM reasoning, scene description, and Sarvam TTS audio streaming.

---

## 2. Choosing the Right Vultr Product

From [Vultr Products](https://docs.vultr.com/products):

| Vultr Product | Best For | Recommended? |
|---|---|---|
| **Vultr Cloud Compute (VPS)** | General microservices, Docker Compose, 24/7 WebRTC workers | **YES (Recommended)** — Lowest latency, lowest cost ($6-$12/mo), full root control. |
| **Vultr Optimized Cloud Compute** | High-traffic commercial deployments with dedicated vCPUs | Optional for production scale. |
| **Vultr Container Engine (VCE)** | Pure serverless container workloads | Good if you prefer managed containers. |
| **Vultr Kubernetes Engine (VKE)** | Large multi-node microservice clusters | Recommended only for enterprise multi-tenant scale. |
| **Vultr Cloud GPU** | Hosting self-hosted LLMs (vLLM / Ollama) locally | Not needed since we use Google Gemini, Groq, and Sarvam APIs. |

---

## 3. Step-by-Step Vultr Deployment

### Step 3.1: Deploy a Vultr Cloud Compute Instance

1. Log in to your [Vultr Customer Portal](https://my.vultr.com/).
2. Click **Deploy +** -> **Deploy New Server**.
3. Choose **Cloud Compute**:
   - **CPU**: Regular Performance or High Performance (AMD or Intel).
   - **Server Location**: Choose the datacenter closest to your target users (e.g., **Mumbai** for India to ensure lowest roundtrip latency to Sarvam AI, or **Singapore / Frankfurt / New York**).
   - **Operating System**: **Ubuntu 24.04 LTS x64**.
   - **Server Size**: **1 vCPU, 2 GB RAM, 50 GB NVMe** (approx. $10 - $12/month) is optimal.
4. In **Additional Features**:
   - Check **Auto Backups** (optional).
   - Expand **Startup Script** and paste the content of [`deploy/vultr-cloud-init.sh`](../deploy/vultr-cloud-init.sh). This automatically installs Docker, Docker Compose, Git, and configures the UFW firewall on first boot!
5. In **SSH Keys**: Select or upload your SSH public key.
6. Set **Server Hostname & Label**: e.g. `drishti-backend`.
7. Click **Deploy Now** and wait ~60 seconds for provisioning.

---

### Step 3.2: Configure Vultr Firewall Group

In Vultr Console:
1. Navigate to **Network** -> **Firewall**.
2. Click **Add Firewall Group** (Name: `drishti-firewall`).
3. Add the following inbound rules:
   - **SSH**: Protocol `TCP`, Port `22`, Source `My IP` (or `0.0.0.0/0`)
   - **Token Server**: Protocol `TCP`, Port `8000`, Source `0.0.0.0/0`
   - **HTTP**: Protocol `TCP`, Port `80`, Source `0.0.0.0/0` (For Caddy / Let's Encrypt)
   - **HTTPS**: Protocol `TCP`, Port `443`, Source `0.0.0.0/0` (For SSL Domain access)
4. Under **Linked Instances**, attach this firewall group to your newly created Drishti instance.

---

### Step 3.3: Connect and Set Up the Project

SSH into your Vultr server:
```bash
ssh root@<YOUR_VULTR_IP>
```

Navigate to `/opt/drishti` (or clone your repository):
```bash
cd /opt/drishti

# If you haven't cloned your repository yet:
git clone <YOUR_GIT_REPO_URL> .
```

---

### Step 3.4: Configure Environment Variables

Create your production `.env` file from the example template:
```bash
cp .env.example .env
nano .env
```

Fill in your actual production API keys:
```ini
# ── LiveKit Cloud Credentials ──
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_key_here
LIVEKIT_API_SECRET=your_secret_here

# ── AI Model Providers ──
LLM_PROVIDER=google
GOOGLE_API_KEY=AIzaSy...
GOOGLE_MODEL=gemini-3.5-flash-lite
SARVAM_API_KEY=your_sarvam_key_here

# ── Optional: Custom Domain for SSL (e.g. drishti.yourdomain.com) ──
DOMAIN=api.yourdomain.com
```
Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

### Step 3.5: Launch Drishti with Docker Compose

#### Option A: Direct Port 8000 (Fastest, no domain required)
```bash
docker compose up -d --build
```

#### Option B: Automated HTTPS / SSL with Caddy (Recommended for production)
If you have pointed a domain (e.g. `api.yourdomain.com`) to your Vultr IP:
```bash
docker compose --profile ssl up -d --build
```
Caddy will automatically provision a free Let's Encrypt TLS certificate for your domain.

---

### Step 3.6: Verify Server Health

Test that the Token Server is live:
```bash
curl http://localhost:8000/health
```
Expected output:
```json
{"status":"healthy","livekit_configured":true}
```

Test generating a token:
```bash
curl "http://localhost:8000/token?room=drishti-room&user=tester"
```

Check agent worker logs:
```bash
docker compose logs -f livekit-agent
```
You should see:
```text
INFO - Worker registered with LiveKit server
INFO - Waiting for connection...
```

---

## 4. Connecting the Android Client

Now that your Drishti backend is running live on Vultr:

1. Open the **Drishti Android App** on your device.
2. Tap the **Settings** icon (or use the token URL dialog).
3. Set the **Token Server URL**:
   - If using direct IP: `http://<YOUR_VULTR_IP>:8000`
   - If using domain with SSL: `https://api.yourdomain.com`
4. The Android app will instantly authenticate, join the LiveKit room, and connect to the agent worker over 4G/5G mobile data from anywhere in the world without requiring ADB or USB cables!

---

## 5. Maintenance & Useful Commands

| Task | Command |
|---|---|
| View real-time agent logs | `docker compose logs -f livekit-agent` |
| View token server logs | `docker compose logs -f token-server` |
| Restart all services | `docker compose restart` |
| Pull updates & rebuild | `git pull && docker compose up -d --build` |
| Stop all services | `docker compose down` |
| Check container resource usage | `docker stats` |

---

## 6. (Alternative) Deploying via Native Systemd without Docker

If you prefer running directly on Ubuntu using Astral `uv` without Docker:

```bash
cd /opt/drishti
chmod +x deploy/systemd/install-services.sh
sudo ./deploy/systemd/install-services.sh
```

Manage the systemd services:
```bash
systemctl status drishti-token-server
systemctl status drishti-agent
journalctl -u drishti-agent -f
```
