# Real QR Check completion report

QR Check uploads the actual selected PNG/JPEG/WEBP image to `POST /api/check/qr`. The backend verifies the file contents, dimensions and pixel count, applies EXIF orientation, then runs ZXing-C++ in a short-lived worker. No AI/OCR guesses QR payloads. Each real code retains the exact decoder text, original bytes in hex, actual position, classification and separate parsed fields. The frontend binds the preview to the returned upload SHA-256 before displaying it. Multiple payloads remain separate.

## Files

Created: `backend/app/routers/qr.py`, `backend/app/services/qr_worker.py`, `requirements-qr.txt`, `tests/test_qr.py`, `scripts/verify_qr.py`, this report, `docs/qr-verification.json`, `docs/qr-browser-verification.json`.

Replaced the old single-code logic in `backend/app/services/qr_service.py`. Updated `backend/app/link_main.py`, `backend/app/main.py`, `backend/app/routers/assessments.py`, `backend/app/database.py`, `backend/app/services/screenshot_upload_limit.py`, `main.js`, `index.html`, `.gitignore` and README. The existing theme, module cards and result tabs are preserved.

## Packages and decoder

No additional packages needed installation in this update. The existing environment provides **zxing-cpp 3.1.1**, Pillow 12.3.0 and python-multipart 0.0.32. `requirements-qr.txt` declares the lightweight runtime. QR_CODE decoding is restricted to QR format, with rotation, inversion and downscale support. One worker executes at a time; each has a 15-second timeout. Cancellation kills and reaps the worker and cleans temporary files. The full request is bounded to 240 seconds.

## Supported payloads

HTTP/HTTPS URL; UPI `upi://pay`; basic vCard/MECARD; escaped Wi-Fi configuration; telephone; email; SMS/SMSTO; ordinary text. Unknown URI schemes return unsupported structured payloads. Other structured payment schemes such as bitcoin/ethereum/lightning are not interpreted. Basic contact parsing does not promise complete vCard support (for example encoded/extended properties).

UPI preserves every parameter including duplicate and unknown parameters, and separately exposes pa/pn/am/cu/tn/tr. Duplicate parameters, incomplete UPI or malformed amounts are reported. Payee names/addresses are self-declared and not ownership verification. Wi-Fi passwords remain temporary in the active result. No payment, network connection, browser navigation, contact import or command is executed.

HTTP/HTTPS QR and contact URLs call the existing protected Link Check, including its SSRF controls. Original raw URLs remain separate from normalized results. Plain text uses the existing Message Check. Decoder observations, deterministic parsing, external findings and Message/AI output remain separate. Decoding alone never produces Low Risk. Missing required checks or unverified identities remain Unable to Assess; actual concerns can raise Caution/High Risk. There are no numerical safety scores.

## Startup commands

From `/Users/thrishalyeggoni/Documents/New project/Safe-Lens-AI`:

```sh
uv pip install --python .venv/bin/python -r requirements-qr.txt
MESSAGE_AI_ENABLED=false .venv/bin/python -m uvicorn backend.app.link_main:app --host 127.0.0.1 --port 8000
```

In a separate terminal:

```sh
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/#/check/qr`. Ctrl+C stops the backend after a test. QR decoding needs no API key, no Ollama and no PaddleOCR. Google Web Risk is an optional configured dependency of Link Check; absent keys are reported, not replaced with a fabricated reputation result.

## Actual browser proof

The controlled `tests/qr-fixtures/https.png` was uploaded in the browser, decoded by ZXing-C++ 3.1.1 and returned exactly **https://example.com** as one QR_CODE. Its classification was URL and parsed original_url matched. The exact upload SHA-256 is recorded in `docs/qr-browser-verification.json`.

Link Check actually resolved DNS, retrieved registry RDAP and performed a TLS-verified HEAD request returning HTTP 200 with zero redirects and no downloaded body. Google Web Risk was unavailable because its key is absent. Final verdict: **Unable to Assess**, not safe.

Copy Destination copied the original value (without adding the normalization slash). Pasting into the Message input produced exactly `https://example.com`. Uploading a different real UPI QR returned a new assessment and payload `upi://pay?pa=controlled%40upi&pn=Controlled+Test&am=12.50&cu=INR&tn=Test&tr=reference-1&custom=preserved`. Parsed values included controlled@upi, Controlled Test, 12.50, INR, reference-1 and preserved unknown custom parameter. Ownership remained unavailable. Retry executed a new decode and produced a new assessment id.

Upload, preview, remove, analyse, cancellation during a multi-URL contact check, retry, reset, back, check another, details, Evidence and Checks were exercised in the browser. Existing drag/drop uses the same file handler; a synthetic drag/drop was not separately exercised. Raw JSON results are captured in the browser verification file. The uploaded QR shown in the result is the original image, with a matching upload hash.

## Tests and limitations

30 QR tests pass. The full relevant regression suite passes **123 tests**, with two live Web Risk tests skipped because no key is configured. Production frontend build and git whitespace checks pass.

Seventeen actual image/API cases are recorded in `docs/qr-verification.json`: HTTPS, provider-approved malicious test URL, plain text, UPI, contact, Wi-Fi, two QR codes, blurred, rotated, small, damaged, no QR, corrupt, unsupported GIF, shortener, punycode and prompt injection. The provider test URL was decoded and passed to real Link Check, but an authoritative malicious reputation match cannot be tested without the key; its observed Caution came from URL structure. Blurred/damaged/no-QR images produced zero readable codes and Unable to Assess; corrupt and GIF uploads were rejected with 422. Rotated and small controlled QR images decoded the exact original payload. Prompt-injection text stayed decoded content and never became instructions.

Limits: 10 MiB, sides 16–6000 pixels, 12 million pixels, nonanimated PNG/JPEG/WEBP, at most 32 codes and 12,000 characters per payload for analysis. At most eight URLs per contact payload are checked; extra URLs are explicitly marked unassessed. Successful decoding does not verify identity, payment authorization or network trust. Non-QR barcodes, exotic QR variants and unsupported payment formats are not promised. AI was disabled throughout live verification and no model was started. A QR from the user's phone was not supplied; browser proof uses controlled real QR images.

History stores only session-authorized metadata. Raw images, QR payloads, Wi-Fi credentials, payment identifiers, contact details and detailed results are not retained in history or logged. Test reports contain controlled, agent-authored values only. Refresh discards detailed browser results and prompts for reupload.

After verification, the backend was stopped. No QR worker, PaddleOCR worker or Ollama process remains running. The frontend remains available with the demonstrated result.
