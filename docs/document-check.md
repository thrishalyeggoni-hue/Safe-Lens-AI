# Document Check: implementation and real verification

Implemented on 13 October 2026. The existing Document module uploads the actual PDF/DOCX, verifies its SHA-256 against the response, and shows real stages, page content, evidence, links, coverage and a separate malware result. The existing theme and module layout are preserved. There are no application fixture responses or document demo verdicts.

## Files and dependencies

Created `backend/app/routers/document.py`, `backend/app/services/document_worker.py`, `backend/app/services/document_scan.py`, `requirements-document.txt`, `tests/test_document.py`, `scripts/create_document_fixtures.py`, `scripts/verify_document.py`, and these verification reports. Replaced `backend/app/services/document_service.py`. Updated `main.js`, the lightweight/full API registration and shutdown in `backend/app/link_main.py` and `backend/app/main.py`, legacy document assessment handling in `backend/app/routers/assessments.py`, upload middleware in `backend/app/services/screenshot_upload_limit.py`, minimal history in `backend/app/database.py`, and existing Message/Qwen services for cached URL reuse and strict document page grounding. README and fixture ignore rules were updated. Earlier module changes remain in the working tree.

Newly installed: python-docx 1.2.0, lxml 6.1.3, and ReportLab 4.5.1 (controlled test fixture authoring only). Existing packages used: pypdf 6.20.1, pdfplumber 0.11.10, pypdfium2 5.14.0, Pillow 12.3.0, PaddleOCR 3.7.0, PaddlePaddle 3.3.1, python-multipart 0.0.32. `uv pip check` checked 112 packages and reported compatibility.

## Pipeline and parser configuration

Multipart bytes are validated by content: PDF signature followed by actual strict parsing, or bounded DOCX ZIP with actual Word content types and document XML. A filename does not establish type. Empty/unsupported files are rejected; uploads are limited to 20 MiB before multipart processing, with bounded multipart overhead. DOCX archives have entry, expansion and compression-ratio limits and macro-bearing content is rejected.

The original bytes enter a private temporary directory and ClamAV scan. A signature match prevents parsing. Parsing runs in a separate process with a 30-second parent deadline, 25-second CPU limit and a requested 1.5 GiB address-space limit. On this macOS host the address-space limit could not be applied; the response explicitly reports `address_space_applied: false`. This is process isolation and bounded execution, not a container or comprehensive operating-system sandbox.

PDFs use strict pypdf parsing, bounded decompression configuration, pdfplumber native text/word coordinates/tables, and a pypdf text fallback. Actual metadata is exposed as observations, never issuer authentication. Annotations preserve actual destinations and rectangles. Visible URL text remains separate from embedded destinations. Visible-domain mismatch is grounded only where a reliable annotation/text coordinate match exists. Inert JavaScript, external-action and embedded-file observations are reported without executing or extracting their payloads.

PDFium renders an inert PNG preview with forms uninitialized and `may_draw_forms=False`. The browser receives this image rather than executing the original PDF. Native text is preferred when meaningful. Image-only pages use the existing local PaddleOCR worker and preserve real page numbers, region IDs, confidence and rendered-pixel polygons. Blank/unreadable pages and skipped pages reduce coverage.

Limits: first 30 PDF pages; up to three rendered pages including the preview; up to three OCR pages; four million rendered pixels/page, maximum side 1600; 12,000 native characters/page and 60,000 total; 16 distinct URL destinations; 30 content-analysis blocks; 300-second total streamed assessment deadline. Truncation, failures and skipped pages are explicit. OCR retains the existing worker timeout/model policy; mixed recognition may require multiple serial recognizer runs.

Supported formats: PDF, including native, scanned and mixed pages; basic DOCX paragraphs, tables, hyperlinks and actual core metadata. DOCX has logical paragraph/table references and `page_number: null`, because a DOCX parser cannot establish rendered pagination. Images, headers, footers, footnotes, endnotes and comments are listed as unprocessed parts and reduce coverage. DOCX image OCR, fixed DOCX pagination, legacy DOC, other office formats and user-provided PDF passwords are unsupported. Encrypted PDFs are not brute-forced.

## Reused analysis and risk policy

HTTP/HTTPS destinations reuse existing Link Check, including DNS/public-address checks, RDAP, pinned-IP verified-TLS HEAD redirect inspection and configured reputation. Links are not opened by the browser; no linked response body is executed. Uncertain OCR URLs are not contacted. Destinations beyond the cap are disclosed.

Each actual page/logical block reuses existing Message Check and its offer/payment rules. Exact quoted spans are checked against that page; OCR evidence maps to real regions. Document observations additionally cover changed payment instructions, guaranteed returns and deposit requests. Pressure or a payment request alone is not proof of fraud. Qwen uses the existing interpreter with a document schema requiring the actual page/reference; wrong-page or unsupported quotes are rejected. No separate document LLM service was introduced.

Malware status and content risk remain separate. No numeric score is fabricated. A clean ClamAV result means no configured known signature matched, not that the document is safe. Missing OCR, parsing, reputation, contextual analysis or coverage cannot silently produce Low Risk. Metadata, company/issuer identity, signature validity, bank ownership, invoice authenticity and document provenance are not independently verified.

## OCR and ClamAV setup

OCR runs locally on CPU with one thread and serialized document/OCR work. Existing explicitly provisioned models are `PP-OCRv5_mobile_det`, `en_PP-OCRv5_mobile_rec`, `devanagari_PP-OCRv5_mobile_rec`, and `te_PP-OCRv5_mobile_rec`. Uploads do not download models. English, Hindi and Telugu controlled scanned files produced actual recognition and page evidence. Mixed recognition produced mistakes and is limited; confidence is not a multilingual accuracy guarantee.

ClamAV 1.5.4 was installed already. `freshclam --stdout` updated/tested the daily database to 28152; actual responses reported `ClamAV 1.5.4/28152/Tue Oct 13 11:56:14 2026`. Signature storage is `/opt/homebrew/var/lib/clamav`. The pipeline requires a daily database no older than seven days. Missing/stale signatures or unavailable/failed/limit-exceeded scans are explicit.

A private foreground clamd receives the actual upload through INSTREAM on a temporary Unix socket (directory 0700/socket 0600), with no TCP listener. One scanner thread, bounded queue/scan size/recursion/file count and a 10-second scan-time setting limit work. Nearby requests reuse the signature database; the daemon stops after 30 seconds idle and on API shutdown. No background system service is installed or enabled. See official [ClamAV signature management](https://docs.clamav.net/manual/Usage/SignatureManagement.html) and [scanning documentation](https://docs.clamav.net/manual/Usage/Scanning.html).

### Exact startup commands

```bash
cd '/Users/thrishalyeggoni/Documents/New project/Safe-Lens-AI'
uv pip install --python .venv/bin/python -r requirements-document.txt
freshclam --stdout
MESSAGE_AI_ENABLED=false .venv/bin/python -m uvicorn backend.app.link_main:app --host 127.0.0.1 --port 8000
```

In a separate terminal, from the same directory:

```bash
npm run dev -- --host 127.0.0.1
```

If ClamAV is absent, install it with `brew install clamav`, configure FreshClam according to the official documentation, and update signatures. `CLAMAV_DATABASE_DIR` can specify the database directory. If OCR models are absent, provision them explicitly with `.venv/bin/python scripts/setup_screenshot_ocr.py`; an upload does not trigger that provisioning. Ollama remained stopped and Message AI disabled during live verification. Google Web Risk remains unavailable until `GOOGLE_WEB_RISK_API_KEY` is configured. Stop the API with Ctrl+C after use; its shutdown stops the private scanner.

## Real end-to-end examples

Controlled PDFs were authored for testing, not used as application defaults. Full actual responses, text, URLs, evidence and OCR polygons are in [document-verification.json](document-verification.json); preview image bytes are intentionally omitted. Actual browser-rendered backend JSON and observed controls are in [document-browser-verification.json](document-browser-verification.json).

Native browser upload: `job_offer.pdf`, validated PDF, 1820 bytes, SHA-256 `3a6d05f60707142ebe4ea5c783b991423f7e687c3a114c49203eaf250470e9ba`, one actual page, one parsed content block, zero OCR runs. Final retry created assessment `asmt_3189cf75faec` rather than reusing the earlier result. Actual page 1 text:

```text
SafeLens controlled document test
This is bank support. Job offer.
Pay INR 2500 registration fee today for your job.
Send me your OTP to verify your account.
Visit https://example.com
```

ClamAV: clean/no configured known signature matched. There was one visible URL and no embedded link in this particular PDF. Link Check actually resolved example.com, retrieved RDAP and completed HEAD HTTP 200 with zero redirects and zero downloaded body bytes; reputation was unavailable because no API key is configured. Exact page 1 evidence included `Pay INR 2500 registration fee` and `Send me your OTP`. Final assessment: **High Risk** from the observed credential request; parsing covered one of one pages, while overall checks were incomplete because contextual AI and reputation were unavailable. Other controlled PDFs supplied real embedded annotations and the visible-domain/destination mismatch case.

Changing the uploaded file to image-only `scanned.pdf` created assessment `asmt_3d6c05705cb1`. It had one actual page with no native text; PaddleOCR really ran and returned five regions with polygons/confidence. Actual reconstructed OCR text:

```text
This is bank support.
Pay INR 2500 registration fee today for your job.
Send me your OTP to verify your account.
Visit https://example.com
Pay via UPI to merchant@okhdfcbank
```

The result preserved `source: ocr`, page 1 and exact matched region boxes, reused real Link Check for the recognized URL and real Message Check for the OTP/payment text, and showed **High Risk** with clean ClamAV status separately. One page was parsed, one page OCR-processed; overall checks remained incomplete. The native upload and different scanned upload produced different hashes, actual content and assessment IDs. Browser proof: [native PDF UI](/tmp/safelens-document-native-check.png), [scanned PDF UI](/tmp/safelens-document-check.png).

## Verification and remaining limits

22 real serialized API cases were completed: normal native PDF, English scanned PDF, mixed native/scanned pages, normal URL, provider-approved malicious-test URL, visible/embedded mismatch, registration-fee job offer, changed-bank invoice, ordinary invoice, Hindi scan, Telugu scan, mixed-language scan, encrypted PDF, corrupt PDF, oversized request, 32-page PDF hitting the 30-page cap, truly blank PDF, standard EICAR attachment PDF, prompt-injection text, inert action PDF and two DOCX files.

The actual embedded [EICAR standard antivirus test fixture](https://www.eicar.org/download-anti-malware-testfile/) matched `Eicar-Test-Signature`; final risk was High Risk and parsing was skipped. It was never executed. The provider-approved malicious URL case returned Caution from URL heuristics, not an authoritative malicious reputation match: the real provider key was unavailable. The 32-page file reported pages 31 and 32 skipped; blank, encrypted and corrupt files did not default to Low Risk. Hindi/Telugu scans returned real credential-request text, but Telugu/mixed recognition showed character errors. An ordinary invoice was Unable to Assess, not authenticated as legitimate.

Browser verification exercised actual file selection/upload, changed-file analysis, remove, Back to input with retained actual file, Reset document, actual retry/cancellation and subsequent completed retry, Check Another with blank input, Review details, actual extracted text, page-linked Evidence and Checks Status with unavailable checks. Existing drag/drop uses the same validated selection handler; a native drag gesture was not separately exercised. One retry initially hit an externally restarted older API and honestly displayed Method Not Allowed; restarting this implementation's lightweight API and resubmitting the retained file completed successfully.

Regression: **144 passed, 2 skipped** across Document, QR, Screenshot, Message and Link suites. Skips require an external reputation key. Qwen page/reference schema and rejection of wrong-page/hallucinated quotations were verified by explicit unit stubs; live Qwen interpretation was not verified because Ollama remained off. Tests with policy stubs are distinct from the real upload/ClamAV/OCR cases above. Production Vite build and whitespace checks passed.

Uploads, rendered pages, OCR intermediates and extracted output are temporary and cleaned after completion/cancellation. History stores minimal session-owned assessment metadata only, without original documents, OCR text, previews or detailed results. Full details remain only in active browser memory and are not recovered from history on refresh. This deliberately authored verification report contains test content only. Backend/scanner/OCR workers are stopped after verification; the frontend remains available. A separate project process has occasionally restarted an older API, so the final process check records the actual state at completion rather than promising persistent control of that launcher.

Final shutdown verification: no listeners on ports 8000, 8001 or 11434, and no remaining uvicorn, clamd, clamscan, document parser, PaddleOCR worker or Ollama processes. The older SafeLens API on port 8001 was also stopped.
