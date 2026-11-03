# 🛡️ FileTrack EDR Agent

<p align="center">
  <b>Advanced Honeyfile-Based Endpoint Detection & Response System</b><br>
  <i>Real-time Threat Detection • Auto-Remediation • Forensic Intelligence • WebSocket C2</i>
</p>

---

## 📌 Overview

**FileTrack** is a lightweight yet powerful Endpoint Detection and Response (EDR) agent designed to detect unauthorized access to sensitive files using **Honeyfiles (Decoy Files)**.

Once triggered, the agent executes a **dynamic incident response playbook** that includes:

* Threat containment
* Automatic recovery
* Forensic evidence collection

With the latest upgrade to **Secure WebSockets (WSS)**, the agent now maintains a full-duplex, real-time connection with the centralized **C2 (Command & Control) Server**, enabling instant remote execution, telemetry collection, and live monitoring.
<p align="center">
  <a href="https://github.com/Youssifa7med/agent-filetrack/releases/tag/v1.0.0"><img src="https://img.shields.io/badge/Release-v1.0.0-brightgreen?style=flat-square"></a>
  <a href="https://github.com/Youssifa7med/agent-filetrack/releases/download/v1.0.0/FileTrack_Setup.exe"><img src="https://img.shields.io/badge/Download-Windows_Installer-blue?style=flat-square&logo=windows"></a>
</p>



## 📥 Download & Installation

Get the latest compiled **Click-to-Install Setup** for Windows. No manual Python configuration or extra dependencies are required.

[![Download FileTrack EDR](https://img.shields.io/badge/Download-FileTrack_Setup.exe-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/Youssifa7med/agent-filetrack/releases/download/v1.0.0/FileTrack_Setup.exe)

> **Note:** The installer automatically configures background execution with the `Highest Privileges` via Windows Task Scheduler. This bypasses UAC prompts and ensures a seamless, stealth deployment on the endpoint.

---


## ✨ Core Features

### ⚡ Real-Time C2 Communication (New)

* Zero-latency command execution using **Socket.IO**
* Full-duplex secure communication
* Replaces traditional HTTP polling architecture
* Instant task execution and live telemetry

---

### 🎯 Precision Honeyfile Monitoring

* Monitors exact decoy files without noisy directory-wide alerts
* Eliminates false positives using:

  * strict path validation
  * event debounce logic
  * intelligent trigger filtering

---

### 🔄 Auto-Remediation (Self-Healing)

* Instantly restores modified or deleted protected files
* Prevents permanent data loss
* Includes loop-prevention mechanisms to avoid recursive restoration triggers

---

### 🛑 Threat Containment

Applies strict OS-level access restrictions using:

```bash
icacls <target_file> /deny Everyone:(F)
```

This immediately locks the compromised file and prevents further attacker interaction.

---

### 🕵️ Advanced Threat Attribution

Identifies the full attacker context including:

* Process ID (PID)
* Executable Name
* Full Command-Line Arguments
* Parent/Child Process Tree Mapping
* Process Relationship Analysis

This enables precise forensic attribution and attacker behavior reconstruction.

---

### 🧵 Threaded Forensic Engine (Asynchronous)

* Non-blocking evidence collection
* Camera, microphone, and screenshots run in isolated threads
* Prevents Event Queue Loops
* Uses strict hardware timeouts to prevent agent freezing

---

## ⚡ Dynamic Incident Response Playbook

Controlled dynamically from the C2 Server using `ACTION_MAP`, with support for runtime parameters.

| Action               | Example Parameter | Description                                    |
| -------------------- | ----------------- | ---------------------------------------------- |
| 📸 `take_screenshot` | N/A               | Capture 3 rapid consecutive screenshots        |
| 🎤 `record_media`    | `record_media:30` | Record webcam + microphone for 30 seconds      |
| 🧠 `dump_memory`     | N/A               | Collect process memory metadata                |
| 🔒 `deny_access`     | N/A               | Restrict file access instantly                 |
| 🔑 `verify_hash`     | N/A               | Validate SHA-256 integrity before/after attack |

---

## 🏗️ Architecture

```text
+--------------------------------------------------+
|            C2 Server & Dashboard                 |
+----------------------+---------------------------+
                       |
      [ HTTP REST ]    |    [ Secure WebSockets ]
      (Registration)   |    (Instant Commands)
                       |
+----------------------v---------------------------+
|                FileTrack Agent                   |
|--------------------------------------------------|
|  Socket.IO Client (Real-Time Listener)           |
|  Watcher Module (OS Event Hooks)                 |
|  Response Engine (Async Forensics Engine)        |
|  Persistence Layer (Startup Registry)            |
+----------------------+---------------------------+
                       |
+----------------------v---------------------------+
|        Protected Endpoints / Honeyfiles          |
+--------------------------------------------------+
```

---

## 📂 Project Structure

```text
FileTrack_Agent/
├── client.py                 # Main Agent Entry Point
├── modules/
│   ├── watcher.py            # Honeyfile monitoring + auto-revert
│   ├── response_engine.py    # Dynamic incident response logic
│   └── socket_handler.py     # WebSocket communication handler
├── evidence/                 # Forensic evidence storage
├── config.json               # Agent configuration
└── requirements.txt          # Dependencies
```

---

## 🚀 Getting Started

### 1️⃣ Install Dependencies

Make sure Python 3.8+ is installed, then run:

```bash
pip install requests watchdog mss psutil opencv-python sounddevice scipy pyaudio python-socketio websocket-client pywin32
```

---

### 2️⃣ Configuration

Edit `config.json` to point to your C2 Server:

```json
{
  "server_ip": "filetrack-2026.duckdns.org",
  "server_port": 5000,
  "secret_key": "FILETRACK_SUPER_SECRET_2026"
}
```

Supports both:

* Local deployment
* Public deployment via DuckDNS

---

### 3️⃣ Run the Agent

Execute as **Administrator** for full containment capabilities:

```bash
python client.py
```

---

## ✔ Agent Startup Flow

Upon execution, the agent will automatically:

1. Perform initial HTTP registration to create a device profile
2. Establish persistent WebSocket communication
3. Apply persistence using Windows Registry (Startup)
4. Start monitoring deployed Honeyfiles
5. Await C2 instructions in real-time

---

## 🔄 Recent Updates

### 📡 Migration to WebSockets

Replaced heavy HTTP polling with `Socket.IO` for:

* instant task execution (`execute_task`)
* live telemetry streaming
* significantly reduced latency

---

### 🎥 Async Media Engine Improvements

Camera and microphone logic migrated to isolated threads with strict timeout controls.

This prevents:

* hardware deadlocks
* missing driver hangs
* blocked agent execution

---

### 🔁 Loop Prevention System

Introduced:

```python
is_reverting = True
```

to prevent infinite trigger loops during file restoration and self-healing operations.

---

### 🌳 Robust Process Tracking

Upgraded process context collection to include:

* Full process tree mapping
* Parent-child relationship tracking
* Graceful handling of:

```text
WinError 1168
Access Denied
```

exceptions without agent crashes.

---

## 📊 Use Cases

### 🎓 Academic Excellence

Graduation Projects focused on:

* Cybersecurity
* DFIR
* EDR Development
* Operating System Internals

---

### 🏢 Enterprise Security

Used for:

* Insider Threat Detection
* Zero-Trust Environments
* Security Monitoring Infrastructure

---

### 🔐 Data Loss Prevention (DLP)

Protects:

* confidential files
* financial documents
* sensitive operational data

---

### 🕵️ Threat Intelligence

Supports:

* attacker behavior analysis
* honeypot intelligence
* adversary profiling

---

## ⚠️ Disclaimer

This project is intended strictly for:

* Educational purposes
* Academic research
* Authorized enterprise security monitoring

❌ Do NOT deploy on systems without explicit user consent.

Unauthorized usage may violate privacy laws and cybersecurity regulations.

---

## 👨‍💻 Authors

### Omar Amr

Cybersecurity Student
Penetration Tester
Web Application Security Specialist


---

## ⭐ Support

If you find this project useful:

* ⭐ Star the repository
* 🍴 Fork the project
* 🛠️ Contribute improvements
* 📢 Share with your cybersecurity community

---

<p align="center">
Built for Security • Designed for Detection • Engineered for Response
</p>
