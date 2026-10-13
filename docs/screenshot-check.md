# Screenshot Check — real implementation and verification

The Screenshot Check page uploads the actual selected PNG/JPEG/WEBP to `POST /api/check/screenshot`. A local PaddleOCR worker returns real recognized text, confidence and polygons. Text is mapped back to OCR regions, then passed through the existing Message Check (which reuses Link Check). The frontend displays the actual original image and exact OCR evidence coordinates. OCR failures and missing contextual/reputation checks do not become Low Risk.

## Files created or modified

Created:

- `backend/app/services/screenshot_image.py`: bounded content-based decoding, EXIF orientation, sanitized filenames and upload hash.
- `backend/app/services/paddle_worker.py`: actual PaddleOCR model invocation in a short-lived child process.
- `backend/app/services/paddle_service.py`: runtime/model capability checks, serialized CPU jobs, timeout/cancellation and temporary-file cleanup.
- `backend/app/services/screenshot_grounding.py`: reading order, precise span-to-region mapping, mixed-language candidate selection, payment observations and explicit uncertain URL candidates.
- `backend/app/services/screenshot_upload_limit.py`: request-body limit, including chunked multipart bodies.
- `backend/app/routers/screenshot.py`: multipart API, real streamed stages and metadata-only session history.
- `scripts/setup_screenshot_ocr.py`: explicit official model downloads; uploads do not download models.
- `scripts/verify_screenshot_ocr.py`: one-process, sequential real OCR verification on controlled fixtures.
- `requirements-screenshot.txt`, `tests/test_screenshot.py`, this guide, and verification reports.

Replaced the old Tesseract screenshot implementation in `backend/app/services/ocr_service.py` with PaddleOCR extraction/orchestration.

Updated `backend/app/config.py`, `backend/app/services/message_service.py` (internal OCR-confidence URL filter), `backend/app/services/message_storage.py`, `backend/app/database.py`, `backend/app/link_main.py`, `backend/app/main.py`, `backend/app/routers/assessments.py`, `main.js`, `index.html`, `style.css`, `vite.config.js`, `.gitignore`, `.env.example` and README. The UI retains its existing layout, colors and animations. Unsupported visual-forgery claims were replaced with accurate descriptions of text/link analysis.

## Packages and OCR models

Already present when this feature started: PaddleOCR 3.7.0, PaddleX 3.7.2, OpenCV-contrib 4.10.0.84, Pillow 12.3.0, python-multipart 0.0.32 and ZXing-C++ 3.1.1.

Installed during implementation: **paddlepaddle 3.3.1**, opt-einsum 3.3.0, protobuf 7.36.2 and safetensors 0.8.0. `uv pip check --python .venv/bin/python` confirmed all installed packages were compatible.

Downloaded these actual PP-OCRv5 models from official PaddleOCR model links:

| Component | Model |
| --- | --- |
| Text detection | PP-OCRv5_mobile_det |
| English recognition | en_PP-OCRv5_mobile_rec |
| Hindi/Devanagari recognition | devanagari_PP-OCRv5_mobile_rec |
| Telugu recognition | te_PP-OCRv5_mobile_rec |

Model files are local under ignored `backend/ocr_models`. Each download has a provenance manifest with its vendor URL and computed archive hash. Runtime requests use explicit local model paths. No cloud OCR is used. See [official PaddleOCR pipeline/model documentation](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html) for model names and returned `rec_texts`, `rec_scores` and `rec_polys` fields.

Processing uses CPU, one inference thread and one worker at a time. Workers unload on completion. Document unwarping, automatic document orientation classification and text-line orientation models are disabled to avoid unnecessary downloads/load. EXIF orientation is corrected. Arbitrary rotations are reported as a limitation rather than silently rotated without evidence. RGB conversion preserves the displayed original; no blind contrast/threshold transforms are applied.

## Exact setup and startup commands

From the project directory:

```bash
cd '/Users/thrishalyeggoni/Documents/New project/Safe-Lens-AI'
uv pip install --python .venv/bin/python -r requirements-screenshot.txt
.venv/bin/python scripts/setup_screenshot_ocr.py
```

Terminal 1 — lightweight API, with Ollama calls disabled for lower load:

```bash
cd '/Users/thrishalyeggoni/Documents/New project/Safe-Lens-AI'
MESSAGE_AI_ENABLED=false .venv/bin/python -m uvicorn backend.app.link_main:app --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend:

```bash
cd '/Users/thrishalyeggoni/Documents/New project/Safe-Lens-AI'
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/#/check/screenshot`.

Optional Qwen text interpretation uses the existing Message Check configuration; omit `MESSAGE_AI_ENABLED=false` when you intentionally want it enabled. This feature did not start Ollama or download a Qwen model. Qwen is reported unavailable in verification results because it was disabled for heat. No AI output was substituted.

Capability probe: `GET /api/check/screenshot/capabilities`. Defaults are 10 MiB image bytes, 6000 pixels maximum per side, 12 million total pixels, a 60-second bound per OCR recognizer and a 240-second total request bound. Multipart request size includes a bounded allowance for form headers. Cold dependency imports can be slow; worker timeouts remain explicit and never imply safety.

## Real browser end-to-end example

The browser uploaded the controlled `tests/screenshot-fixtures/otp.png` (1100 × 410). Its actual content is:

```text
This is bank support.
Pay INR 2500 registration fee today for your job.
Send me your OTP to verify your account.
Visit https://example.com
Pay via UPI to merchant@okhdfcbank
```

The original uploaded image is preserved as a local browser File/object URL, not replaced by a generated preview. The frontend compares its SHA-256 with the actual uploaded bytes hashed by the backend before displaying any result. The verified hash was `e316fe091c90268b3d99d2e48915f11937b65e96447600778be60e17dfc01cee`.

Actual OCR output:

| Region | Recognized text | Actual confidence | Actual polygon points |
| --- | --- | ---: | --- |
| ocr_1 | This is bank support. | 0.9759753942 | (33,31), (367,36), (367,83), (32,79) |
| ocr_2 | Pay INR 2500 registration fee today for your job. | 0.9855439067 | (29,101), (806,101), (806,158), (29,158) |
| ocr_3 | Send me your OTP to verify your account. | 0.9928420186 | (31,172), (706,172), (706,222), (31,222) |
| ocr_4 | Visit https://example.com | 0.9912926555 | (32,241), (438,245), (437,293), (31,290) |
| ocr_5 | Pay via UPI to merchant@okhdfcbank | 0.9739292264 | (28,311), (648,309), (648,361), (28,363) |

These are raw model confidence scores, not risk percentages and not guarantees of correct recognition.

Message Check extracted an identity claim, advance-fee request, urgency and a credential request. For example, `Send me your OTP` maps to **ocr_3** and polygon **[(31,172),(706,172),(706,222),(31,222)]**. Selecting that finding in the browser drew precisely that polygon on the original screenshot. No arbitrary warning rectangle was used.

The OCR URL `https://example.com` went through the existing real Link Check service. DNS resolved public records; registry RDAP was available; TLS-verified HEAD inspection completed. Google Web Risk was unavailable without its API key. URL verdict: **Unable to Assess**. The exact returned observations are in the browser verification JSON.

Final screenshot verdict: **High Risk**, based on a clear OTP-disclosure request. This does not verify sender identity, account ownership, payment legitimacy or screenshot authenticity. Qwen interpretation remained unavailable, honestly disclosed.

Your supplied `SafeLens AI’s three-screen clarity.png` was also uploaded through the actual browser, not just a fixture. It decoded as PNG, 2172 × 724, returned 62 real OCR regions, 12 uncertain regions and the visible `https://example.com` URLs. That run returned **Unable to Assess**. OCR split adjacent pieces of one text line, exposing a reading-order issue; the final implementation groups spatial rows, orders adjacent pieces left-to-right, and preserves distant columns separately. Layout ordering remains heuristic and does not establish message authorship or context.

Changing the upload produced a different hash, assessment ID, OCR output and findings. User-image details are not stored in application history; the report retains only validation summary metadata for that upload.

## Tested languages and inputs

Real OCR was executed sequentially on 17 controlled screenshot cases. Hindi, Telugu and mixed fixtures were rendered in the browser to preserve native script shaping instead of relying on unshaped Pillow text.

- English OTP and advance-fee examples produced the expected high-risk deterministic indicators.
- Hindi recognized `अपना ओटीपी भेजें` correctly.
- Telugu recognized `మీ ఓటీపీ పంపండి` correctly, but another line lost vowels in several words despite high confidence. Practical Telugu coverage is limited, not guaranteed.
- Mixed English/Hindi/Telugu safety warnings were recognized, with the different real recognizers mapped back to their selected region outputs. Confidence values across different models are not comparable calibrated accuracy.
- Ordinary conversation, `Never share your OTP`, educational/quoted warnings, payment references, legitimate URLs and several URLs were processed using real output and existing services. Benign content remained Unable to Assess when required AI or reputation checks were unavailable.
- Prompt-injection text followed by an OTP request remained message content; the deterministic verdict stayed High Risk.
- A blurred image and a no-text image produced zero regions and did not become Low Risk.
- A 90-degree rotated image without EXIF recovery produced low-confidence gibberish and remained Unable to Assess.
- A low-resolution image preserved the OTP request but misread `https://` as `https:/`. The final implementation records an explicit uncertain URL candidate, its original text, inferred candidate and reason, and does not silently contact a repaired domain.
- Corrupt bytes, unsupported GIF, wrong MIME/extension claims, oversized dimensions, pixel limits, EXIF orientation, byte limits, session ownership and cancellation cleanup are tested.
- A real QR payment matrix was decoded using ZXing-C++ as a separate evidence source. QR-specific account/payment/destination safety is not claimed by this screenshot flow.

The provider-approved malicious test URL was sent through the real Link Check path, but its authoritative threat match could not be verified without `GOOGLE_WEB_RISK_API_KEY`. Live provider tests explicitly skip instead of fabricating a positive result.

## Evidence, privacy and limitations

Every accepted text finding must exactly match the reconstructed OCR text and map to actual known OCR region IDs, polygons and scores. Missing or invented mapping is rejected. Low OCR scores mark findings uncertain; they can reduce High Risk to Caution when the decision depends on uncertain wording. An actual clear credential request or a confidently extracted authoritative URL threat match can still justify High Risk even when other coverage is incomplete. Low Risk requires the underlying Message/Link checks to be complete and excludes OCR uncertainty, unsupported coverage, ambiguous mixed processing, inferred URL repairs and unevaluated QR content.

OCR is not visual forensic analysis: altered digits, cloned pixels, financial authenticity and sender/payee identity are unverified. Multi-column layouts, tiny text, blur, unusual rotations, stylized fonts and unfamiliar scripts may be misread. The 0.80 readability threshold is a policy cutoff, not a calibrated probability. OCR may omit text entirely; no completeness guarantee is made.

The original upload is held transiently for decoding and a normalized RGB image is written only to a private temporary directory while its OCR worker runs. That directory is removed on success, failure, timeout or cancellation. Filenames do not become server paths. Workers have bounded output/time, never execute uploads, and do not emit user OCR content into API logs. Screenshot/API JSON contains no raw image bytes or server filesystem paths. The client retains a local File only for the active view/back/retry flow; Reset clears it. Refresh requires a new upload.

Session history contains only generic module/ID/timestamps/risk metadata. No filename, screenshot bytes, OCR text, payment identifier, URL, evidence box or AI output is saved in screenshot history. Responses use `Cache-Control: no-store` and retrieval enforces session ownership. No cloud OCR is used. Readable extracted URLs contact DNS/RDAP/destinations and configured reputation services, as disclosed in the intake form.

Verified controls: upload/preview, remove, Analyse, retry, Cancel, Reset, Back to input, Check another, Review details, Evidence and Checks tabs, and precise finding highlighting. Existing drag/drop uses the same selected-file handler; it has not been separately driven by the browser automation. The dev watcher ignores runtime/history/build files so transient evidence is not refreshed by runtime writes.

## Validation commands and reports

```bash
.venv/bin/python -m pytest tests/test_screenshot.py tests/test_message.py tests/test_message_api.py tests/test_link.py tests/test_link_api.py -q
npm run build
uv pip check --python .venv/bin/python
```

Validation: **93 passed, 2 skipped** (missing live Web Risk key), production build passed, package compatibility passed.

`screenshot-ocr-verification.json` records actual sequential OCR runs on controlled screenshots. `screenshot-browser-verification.json` records the controlled browser submission, exact result and tested interactions. Application code never uses these files to generate findings. Backend API, OCR workers and Ollama are stopped after the brief tests.
