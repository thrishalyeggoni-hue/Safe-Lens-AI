# Offer Check — real text/documents and grounded shared Qwen

Implemented 14 October 2026. The existing Offer module submits actual pasted text or one PDF/DOCX separately. It performs offset-preserving extraction, contextual deterministic checks, shared Link/Message/Qwen analysis, and returns actual evidence and limitations. No seeded offer verdict, score, market-price comparison, company registration or regulatory lookup is fabricated.

## Files and reused services

Replaced `backend/app/services/offer_service.py`; created `backend/app/routers/offer.py`, `scripts/verify_offer.py`, `docs/offer-verification.json` and live Qwen verification files. Updated `main.js`, API registration, upload limits, legacy offer handling, metadata-only history, and the existing `message_service.py`/`message_ai.py` to use an offer context and bounded offer schema. Regression tests are in `tests/test_media_offer.py`. No new model/framework or API key was installed for Offer Check.

Reused: existing Message Check entity extraction, language/script screening, request context and negation/quotation handling; protected Link Check; existing local Ollama/Qwen interpreter and quote validation; actual Document Check (ClamAV, parser, scanned-page OCR, coverage and page references). Uploaded offers use Document Check's real per-page results; there is no duplicate PDF/OCR/URL parser. Embedded destinations remain in the document analysis and top-level URL results.

Supported offer type cues: job, shopping, investment, service and promotion. Competing or absent cues produce `unknown`, not forced classification. Keyword type cues are observations, not certified classification. Extracted contacts, monetary amounts, organisation mentions/claims, URLs and payment/pressure spans preserve exact original text and Unicode code-point offsets. A lexical contact-domain inconsistency is a weak observation, not proof of impersonation or an official-domain check.

Offer-specific rules cover actual fee/deposit wording, guaranteed-return claims, claimed large discounts, pressure, off-platform payment, seed/private-key requests and regulatory claims. Existing Message rules cover OTP/password, unusual payment, remote access, contact channels and Hindi/Telugu targeted request patterns. Safety advice, negation, educational and quoted content remain distinguishable. A fee mention alone is not confirmed fraud; an ordinary application deadline is not automatically a scam. No salary/price benchmark, licence, bank/phone ownership or issuer authenticity is invented.

## Qwen grounding and limits

Existing local interpreter only: no tools, environment access or cross-user data. The offer is untrusted user content, never a system prompt. Schema/Pydantic validation requires category, exact evidence, interpretation, recommended action, uncertainty and context. The offer schema caps output at two most consequential concerns to keep this laptop's processing bounded. Findings are accepted only when evidence is present at actual offsets; unsupported external factual assertions are rejected. Document page schema validates the actual page/logical reference; OCR findings must map to real regions. Raw model output remains distinguishable from deterministic findings and overall risk.

Default existing configuration is `qwen3:4b`; the smaller already cached **qwen2.5:3b** was selected via environment for live Offer verification. Local Ollama version: **0.40.0**. Actual model digest: `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`. No checkpoint was downloaded. Offer inference uses one CPU thread for model options (Ollama can use local Metal), bounded output of 600 tokens, 8192 context and conservative full-prompt byte validation. Model reuse is temporary with `keep_alive: 0`, up to two schema attempts and bounded request deadlines; no model remains intentionally resident after verification.

Live attempts initially timed out or produced schema-invalid output; they were exposed as unavailable and never substituted. Limiting the offer schema enabled a real valid response. [offer-qwen-live-success.json](offer-qwen-live-success.json) records actual API output for `Send your OTP to activate this job offer.` Qwen produced exact `Send your OTP` evidence at offsets **0–13**, with credential-request interpretations and uncertainty that sender legitimacy cannot be established from text. The model repeated that concern twice; this is actual output and a model-quality limitation, not independent corroborating evidence. Deterministic risk was High Risk regardless. Earlier failed attempts remain in their own verification records. Live model success on these controlled English inputs does not establish broad accuracy or reliable multilingual contextual analysis.

## API, privacy and frontend

`POST /api/check/offer` accepts JSON `{ "offer": "actual text" }` or multipart `file` and optional OCR `language`. Submit text or a document separately to preserve a single source for offsets; simultaneous text/document is rejected clearly. Text maximum is 12,000 Unicode characters, with controls/URL-count limits from Message Check. Documents are bounded to 20 MiB and reuse Document limits. Real stages stream via `?stream=true`; disconnect/cancel aborts processing. Raw uploads/pages/OCR are temporary; history retains only session-owned assessment metadata, not offer text, bank/credential/contact data or details. Preview bytes are omitted from verification JSON, never replaced by invented extracted content.

The existing UI keeps its theme and structure. Paste/upload, analysis, Back with retained actual input, retry, cancel, remove, reset, Check Another, Review details, Evidence and Checks share the established controls. Actual full original text, classification/entities, Qwen output, page-linked document details and real Link Check results are inspectable. No fake progress percentage or simulated timer is used for these modules. Details disappear on refresh because history intentionally contains no submitted content.

## Actual controlled verification

[offer-verification.json](offer-verification.json) includes 20 actual text submissions: ordinary job, registration-fee job, company/contact-domain discrepancy, negated fees, ordinary shopping, claimed 90% discount, crypto shopping, ordinary investment explanation, guaranteed-return investment, seed phrase, ordinary URL, provider-approved malicious-test URL, no URL, Hindi, Telugu, mixed language, ambiguous short text, warning article, quoted scam and injection content. Four real files also ran: native job PDF, scanned PDF with real OCR, job DOCX and encrypted PDF. Most batch cases ran with AI explicitly disabled to isolate available extraction/rules/URL behavior and avoid continuous model load.

Observed examples: registration fee plus job/pressure produced High Risk; domain mismatch alone Caution; guaranteed returns plus immediate crypto payment High Risk; negated fees/warnings/quoted scams did not become active demands; encrypted document Unable to Assess. The provider-approved malicious-test URL was only Caution from available heuristics because no authoritative reputation key was configured. No fake external match was returned. Hindi/Telugu/mixed examples exercised actual targeted text rules, not a general multilingual accuracy claim.

The browser submits the actual full test offer:

```text
Job offer: Pay INR 3000 registration fee today. Send your OTP to activate the offer. Visit https://example.com. Contact hr@unrelated.example.
```

This contains a job cue, amount `INR 3000`, payment request, pressure, credential request, contact email and actual URL. Shared Link Check performs available DNS/RDAP/HEAD checks; Google Web Risk is unavailable without its key. Exact evidence stays tied to the submitted offsets; final content risk is High Risk from the observed request combination, while employer legitimacy and contact ownership are unverified. Browser output and changed-input verification are recorded separately in `offer-browser-verification.json`.

Unsupported external verification: company registration, merchant/brand authorisation, SEBI/RBI or other licensing, salary/market prices, investment performance, phone/bank ownership, signature authenticity and criminal records. These remain unavailable even if contextual Qwen succeeds. Suspicious content never establishes confirmed fraud by itself.

## Startup

Low-heat extraction/rules/Link/Document mode:

```bash
cd '/Users/thrishalyeggoni/Documents/New project/Safe-Lens-AI'
MESSAGE_AI_ENABLED=false .venv/bin/python -m uvicorn backend.app.link_main:app --host 127.0.0.1 --port 8000
```

For the verified cached Qwen model, briefly run Ollama in one terminal:

```bash
OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 ollama serve
```

Then run the API in another terminal:

```bash
cd '/Users/thrishalyeggoni/Documents/New project/Safe-Lens-AI'
MESSAGE_AI_ENABLED=true MESSAGE_OLLAMA_MODEL=qwen2.5:3b .venv/bin/python -m uvicorn backend.app.link_main:app --host 127.0.0.1 --port 8000
```

Frontend, from the same directory:

```bash
npm run dev -- --host 127.0.0.1
```

Document uploads require the already configured Document dependencies/signatures/OCR models; see [Document setup](document-check.md). Stop API and Ollama with Ctrl+C after use. Web Risk needs its existing optional key for authoritative URL reputation; Offer orchestration itself needs no new API key.

Browser full-text assessment `asmt_856f7e3c1bcf` extracted amount `INR 3000` at 15–23, email `hr@unrelated.example` at 120–140 and the actual example.com URL. Its contextual request timed out and was explicitly unavailable. Changing to the shorter credential request generated `asmt_6fc5e88e12f0`; real Qwen returned two grounded interpretations with 0–13 evidence offsets, shown in the frontend. This demonstrates real input-dependent results and visible model limitations, rather than reliable AI for every longer offer.

Validation: full regression suite 161 passed, 2 external-provider checks skipped; after final model/boundary changes, the affected suites passed 69 tests with 1 external-provider skip. Production build, package compatibility and whitespace checks passed. A direct real worker check confirmed transparent-image compositing, then exited. No guarantee of general model accuracy is inferred.

Final shutdown: no API/model listeners on ports 8000, 8001 or 11434 and no remaining FFmpeg/media/OCR/document/ClamAV/model processing workers. The auto-restarting Homebrew Ollama service was stopped as requested for laptop heat. Frontend left running.

Actual browser PDF upload produced `asmt_eda545936427` with the original file SHA-256, real ClamAV result, Page 1 text and grounded offer evidence. Retained-file retry completed as `asmt_5c6511b1ede7`. The browser then navigated to a Link result, so the detailed retry response was not captured. Check Another blanking is implemented; its final control fix and native drag/drop were not separately exercised.

Final grounding guards also reject unsupported regulator-licensing assertions and market-value comparisons. The focused Media/Offer/Message suite passed 47 tests after this change.
