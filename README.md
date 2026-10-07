# SafeLens AI — Before you click.

SafeLens AI is a modern threat assessment platform designed to evaluate suspicious links, messages, screenshots, QR codes, documents, media files, and financial offers using real-time heuristic security engines, local machine learning models (Ollama + Qwen), and antivirus scanners.

---

## 🛡️ Core Threat Modules

1. **Link & Phishing Check**: Real-time URL normalization, domain age verification, DNS trace analysis, homoglyph / punycode detection, and Google Safe Browsing API v4 integration.
2. **Message & Social Engineering Check**: Detects artificial urgency, OTP lures, advance fee scams, and authority impersonation using deterministic pattern matchers and local Ollama Qwen semantic reasoning.
3. **Screenshot & OCR Check**: Extracts on-screen text and payment details using high-contrast image preprocessing and PaddleOCR / Tesseract OCR engines.
4. **QR Code Decoder**: Parses matrix payloads using ZXing-C++ (`zxingcpp`) and extracts URLs, vCards, Wi-Fi parameters, and UPI transaction payment structures (`pa`, `pn`, `am`, `cu`).
5. **Document & Invoice Inspector**: Scans PDFs using `pdfplumber` and `pypdf` for active `/JavaScript` launch actions, suspicious macro markers, structured payment tables, and scans for malware signatures via ClamAV (`clamscan`).
6. **Media & Keyframe Inspector**: FFmpeg-powered video container inspection, keyframe OCR sampling, and OpenAI Whisper audio speech-to-text transcription.
7. **Job & Investment Offer Evaluator**: Evaluates high-yield investment scams, crypto deposit demands, task fraud, and unverified company domains.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Node.js** (v18+)
- **Python** (v3.10+)
- **FFmpeg** (`brew install ffmpeg`)
- **Tesseract OCR** (`brew install tesseract`)
- **ClamAV** (`brew install clamav`)
- **Ollama** (`brew install ollama` with `qwen2.5:3b`)

### 2. Frontend Setup
```bash
# Install dependencies
npm install

# Start development server (port 5173 with API proxy to port 8000)
npm run dev
```

### 3. Backend Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Start backend server
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 🧪 Testing & Evaluation

### Run Test Suite
```bash
PYTHONPATH=. pytest tests
```

### Run UCI Benchmark Evaluation
```bash
python evaluation/evaluate_messages.py
```

---

## 🔒 Privacy & Architecture
- **Stateless & Transient Evaluation**: Uploaded files and texts are evaluated locally or in temporary sandbox memory and purged automatically according to retention policy.
- **Device-Local Session Telemetry**: Metrics are stored in local SQLite databases keyed to private, device-local session cookies and never transmitted to external telemetry trackers.

---

## 📄 License
MIT License © 2026 SafeLens AI.
