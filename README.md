# SafeLens AI — Before you click.

SafeLens AI is a modern threat assessment platform designed to evaluate suspicious links, messages, screenshots, QR codes, documents, media files, and financial offers using real-time heuristic security engines, local machine learning models (Ollama + Qwen), and antivirus scanners.

---

## Core threat modules

1. **Link Check**: URL normalization, public-address DNS checks, RDAP registration data, bounded redirects, and Google Web Risk reputation when configured.
2. **Message Check**: Grounded credential, urgency, payment, and impersonation indicators, with optional local Ollama/Qwen interpretation.
3. **Screenshot Check**: Local PaddleOCR text, confidence, polygons, and reused Message/Link analysis.
4. **QR Check**: Real ZXing-C++ decoding of links, payment, contact, and Wi-Fi payloads.
5. **Document Check**: Bounded PDF/DOCX parsing, ClamAV malware scanning, scanned-page OCR, and exact document evidence.
6. **Media Check**: Actual image/video/audio decoding, sampled-frame OCR, local Whisper transcription, timestamped evidence, and cancellable jobs.
7. **Offer Check**: Pasted text or PDF/DOCX review for fees, guarantees, credential requests, pressure, and contact inconsistencies.

Unavailable checks are disclosed. Deepfake/voice-clone detection is not configured. Whisper tiny is unreliable for Hindi/Telugu speech; longer Qwen requests can time out. Company identity, regulatory registration, and market prices are not independently verified.

## Local setup from a fresh clone (macOS)

Existing configured laptops do not need to reinstall dependencies or redownload cached models. A GitHub push does not deploy the app or transfer your local services.

### 1. Clone and install dependencies

Install Git, Node.js 18+ and Python 3.11 or 3.12 first. With Homebrew installed:

```bash
git clone https://github.com/thrishalyeggoni-hue/Safe-Lens-AI.git
cd Safe-Lens-AI
brew install ffmpeg clamav ollama
npm ci
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-document.txt -r requirements-media.txt -r requirements-qr.txt pytest pytest-asyncio
```

These feature requirements include the shared Link, Message, Screenshot, and Offer dependencies. Paddle wheels depend on your Python/OS architecture; these instructions target the tested macOS setup.

### 2. Configure the backend

```bash
cp -n .env.example .env
```

Edit the repository-root `.env`:

```dotenv
GOOGLE_WEB_RISK_API_KEY=YOUR_GOOGLE_WEB_RISK_KEY
OLLAMA_BASE_URL=http://127.0.0.1:11434
MESSAGE_OLLAMA_MODEL=qwen2.5:3b
MESSAGE_AI_ENABLED=true
```

Enable Google Web Risk in a Google Cloud project with billing and create an API key restricted to that API. Keep the key only in the ignored `.env`; see [Google's setup guide](https://docs.cloud.google.com/web-risk/docs/using-sample-app). Leaving it blank explicitly disables reputation checks. Restart the API after changing configuration. The older `backend/.env.example` describes legacy configuration; use the root `.env.example` for this runtime.

### 3. Provision local models and antivirus signatures once

```bash
.venv/bin/python scripts/setup_screenshot_ocr.py
.venv/bin/python -c 'import whisper; whisper.load_model("tiny", device="cpu")'
```

The Whisper setup command downloads and briefly loads the tiny checkpoint into its standard cache. Uploads never download models.

For a fresh Homebrew ClamAV install, locate `$(brew --prefix)/etc/clamav/freshclam.conf.sample`, copy it to `freshclam.conf` if there is no existing configuration, and comment out its `Example` line. Then run:

```bash
freshclam --stdout
```

Use the [ClamAV configuration guide](https://docs.clamav.net/manual/Usage/Configuration.html) if FreshClam reports a configuration/permission error. Refresh signatures regularly; the app rejects signatures older than seven days. The private scanner starts on demand and stops after idle or API shutdown.

### 4. Run in three Terminal tabs

In the first tab:

```bash
OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 ollama serve
```

On a fresh machine, run `ollama pull qwen2.5:3b` in another tab once while Ollama is running. It is already cached on the original development laptop.

In the second tab, from the repository root:

```bash
.venv/bin/python -m uvicorn backend.app.link_main:app --host 127.0.0.1 --port 8000
```

In the third tab, from the repository root:

```bash
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173/. Stop the API and Ollama with Ctrl+C after use. For less heat, set `MESSAGE_AI_ENABLED=false` and leave Ollama stopped; extraction and deterministic checks remain available with AI explicitly unavailable. No persistent background service is required.

### What GitHub contains

Source code for all seven features, UI assets, dependency manifests, model provisioning/fixture scripts, tests, and verification reports are included. `.env` secrets, `.venv`, `node_modules`, downloaded model weights, local databases, uploaded files, generated fixtures, and build caches stay local. Install/provision them using the steps above on a new machine. Verification reports describe controlled test inputs and actual observations, not bundled runtime responses.

---

## 🧪 Testing & Evaluation

### Run Test Suite
```bash
PYTHONPATH=. .venv/bin/python -m pytest tests
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

## Real Link Check (lightweight runtime)

Use `.venv/bin/python -m uvicorn backend.app.link_main:app --host 127.0.0.1 --port 8000` to run all seven check endpoints and history without loading models at startup. See [the implementation and run guide](docs/link-check.md) for dependency setup, Web Risk credentials, request safety, field provenance, risk policy, and tests. Reputation is unavailable until `GOOGLE_WEB_RISK_API_KEY` is configured; unavailable checks never silently become Low Risk.

## Real Message Check

The same lightweight runtime also serves `POST /api/check/message`. The frontend sends exact pasted text, highlights original evidence, reuses real Link Check for embedded URLs, and reports local Qwen availability. Message history retains only metadata. See [the Message Check implementation and verification report](docs/message-check.md) for startup commands, actual browser results, configuration, privacy, and limitations. Real Qwen inference timed out during verification; no AI output was substituted.

## Real Screenshot Check

`POST /api/check/screenshot` accepts a multipart PNG/JPEG/WEBP upload. Real local PaddleOCR returns recognized text, scores and polygons; grounded text reuses Message and Link Check. The browser displays the actual original image and exact OCR boxes. Models are provisioned explicitly; one CPU worker runs at a time and exits after OCR. No screenshot content is saved in history. See [the Screenshot Check report](docs/screenshot-check.md) for setup, browser evidence, tested languages and limitations.

## QR Check

Real multi-code ZXing-C++ upload decoding, protected Link Check reuse and temporary payment/contact/Wi-Fi parsing. See [QR Check implementation and verification](docs/qr-check.md). Start the lightweight API with `MESSAGE_AI_ENABLED=false .venv/bin/python -m uvicorn backend.app.link_main:app --host 127.0.0.1 --port 8000`; no OCR/AI model is required.

## Real Document Check

`POST /api/check/document` processes actual PDF/DOCX uploads through ClamAV, isolated parsing, bounded scanned-page PaddleOCR and existing Link/Message analysis. Exact page evidence, separate malware status and incomplete coverage are disclosed. See [Document Check implementation, setup and real verification](docs/document-check.md). The lightweight startup command keeps Ollama off; the private scanner stops after idle or API shutdown.

## Real Media Check

Actual image/video/audio decoding, bounded FFmpeg sampling, local PaddleOCR and Whisper, timestamped Message/Link evidence, and persisted cancellable jobs. Specialist deepfake/audio authenticity is explicitly unavailable. See [Media setup, hardware and verification](docs/media-check.md).

## Real Offer Check

Actual pasted offers or PDF/DOCX inputs reuse Message, Link, Document and grounded local Qwen analysis. Fees, guarantees, contact inconsistencies and credentials are contextual indicators, not invented external verification. See [Offer setup and real verification](docs/offer-check.md).
