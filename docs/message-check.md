# Real Message Check — implementation and verification

Message Check now submits the original text to `POST /api/check/message`, uses contextual deterministic evidence and the existing real Link Check service, and renders the returned assessment. Local Qwen integration is implemented, but successful real inference is **not verified**: the available Qwen3 model timed out during the final browser test. There is no replacement AI output.

## Files

Created: `backend/app/services/message_extraction.py`, `message_ai.py`, `message_storage.py`, and `backend/app/routers/message.py`.

Replaced the former keyword/demo message processing in `backend/app/services/message_service.py`.

Updated: `backend/app/config.py`, `backend/app/database.py`, `backend/app/main.py`, `backend/app/link_main.py`, `backend/app/routers/assessments.py`, `.env.example`, `main.js`, `index.html`, `style.css`, `tests/test_message.py`, `tests/test_message_api.py`, and README. The existing Link Check services are reused without a second scanner. `docs/message-check-verification.json` contains only controlled test data captured from the rendered browser result, not private user content.

## Dependencies and model

No new packages were installed for this Message Check change. Existing FastAPI, Pydantic, pydantic-settings, HTTPX, SQLAlchemy, dnspython and tldextract packages provide the runtime. Tests use pytest/pytest-asyncio. No language-detection library was installed: Unicode script screening is explicitly reported as limited rather than advertised as comprehensive language detection.

Ollama was already installed at `/opt/homebrew/bin/ollama` (version reported locally: 0.40.0). The final test discovered `qwen3:4b` with digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`, but the actual chat call returned `ReadTimeout`. No successful Qwen output or evaluated model quality is claimed.

Configuration:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
MESSAGE_OLLAMA_MODEL=qwen3:4b
MESSAGE_AI_ENABLED=true
```

Defaults: maximum 12,000 Unicode code points and eight distinct URLs; maximum two URL checks concurrently. The model request uses schema-constrained JSON, separate system/user roles, `think=false`, `temperature=0`, `num_thread=2`, `num_ctx=8192`, `num_predict=1200`, and `keep_alive=0` to unload after requests. Model output is bounded to 256 KiB. Invalid JSON/schema gets at most one retry; transport failures do not retry. A conservative full-prompt byte budget skips inference instead of silently truncating message content.

To enable Qwen later, when comfortable with the laptop load, use separate terminals:

```bash
ollama serve
```

```bash
ollama pull qwen3:4b
```

`ollama run qwen3:4b` is the interactive alternative. The website calls `/api/tags` and `/api/chat` itself. Setting `MESSAGE_AI_ENABLED=false` disables calls entirely. The Qwen model is documented at https://ollama.com/library/qwen3:4b and structured-output behavior at https://docs.ollama.com/capabilities/structured-outputs.

## Exact startup commands

Terminal 1:

```bash
cd '/Users/thrishalyeggoni/Documents/New project/Safe-Lens-AI'
.venv/bin/python -m uvicorn backend.app.link_main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
cd '/Users/thrishalyeggoni/Documents/New project/Safe-Lens-AI'
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/#/check/message`. This lightweight API avoids importing Torch, OCR, media processing or an in-process LLM. It serves Link Check, Message Check and session history. Stop the API using Ctrl-C. Both the API and Ollama were stopped after verification; the separately configured Homebrew Ollama service was also stopped to prevent automatic restart.

## Real browser example

The exact original submission, including two spaces at each end, is shown as a JSON string:

```json
"  😀 This is bank support. Pay ₹2,500 registration fee today for your job. Send me your OTP to verify your account. Visit https://example.com  "
```

Final browser result: `asmt_4d4ce8fac187`, timestamp `2026-10-13T16:07:46.221246+00:00` (see the captured JSON for authoritative timestamp).

Offsets are zero-based Unicode code points with an exclusive end. The frontend uses `Array.from` to avoid emoji breaking highlighting.

| Category | Exact evidence | Start | End |
| --- | --- | ---: | ---: |
| Identity claim | This is bank | 4 | 16 |
| Amount entity | ₹2,500 | 30 | 36 |
| Advance-payment rule | Pay ₹2,500 registration fee | 26 | 53 |
| Urgency | today | 54 | 59 |
| Credential request | Send me your OTP | 74 | 90 |
| URL entity | https://example.com | 121 | 140 |

Embedded URL used the existing actual Link Check pipeline:

- Normalized URL: `https://example.com/`.
- DNS resolved public IPv4/IPv6 addresses; exact records and timestamps are captured in the JSON.
- RDAP returned registration `1995-08-14T04:00:00Z`, expiry `2027-08-13T04:00:00Z`, and registrar `RESERVED-Internet Assigned Numbers Authority`.
- TLS-verified, public-IP-pinned HEAD inspection returned HTTP 200, zero redirects and zero downloaded body bytes.
- Google Web Risk was **unavailable** because `GOOGLE_WEB_RISK_API_KEY` is not configured. URL verdict: **Unable to Assess**, not a claim of safety.

Qwen structured output was exactly:

```json
null
```

AI status was `unavailable`, with `ReadTimeout`; no model output was fabricated. Message verdict was **High Risk** because the original message directly requests disclosure of an OTP. This verdict does not authenticate the sender or establish criminal activity.

A separate real browser submission of `Never share your OTP with anyone.` returned **Unable to Assess**, with the OTP reference classified as `safety_advice_or_negated`, not a direct scam request. AI was unavailable (`ConnectError`). Changing text produced a different assessment ID.

## Privacy and behavior

Only ID, session ownership, timestamps, module and risk plus generic metadata are saved. Raw text, entities, embedded URLs, evidence, model output and secrets are not persisted in message history. Full results exist transiently in the response/current browser view. Refresh shows metadata and asks for the message again. The original textarea retains the text for Back to input; Reset clears it and the displayed detailed result. The endpoint sets `Cache-Control: no-store`. API errors avoid quoting submitted content.

Embedded URLs contact real DNS/RDAP/destinations and configured reputation providers, as disclosed in the intake form. An enabled local model receives the exact text. No remote model fallback exists.

Analyse, Cancel, Reset, Back to input, Check another, detail disclosures, Checks Status and evidence highlighting were exercised in the real browser. All evidence is rendered using text nodes rather than pasted HTML. Cancel aborts the frontend request and cancels the streaming analysis task.

## Policy and limitations

An authoritative malicious URL match gives High Risk even in a warning, with an explanation that the destination risk does not prove sender fraud. A contextual direct credential-disclosure request gives High Risk. Advance payment plus pressure plus a job/identity claim gives High Risk. Weaker direct indicators or grounded AI concerns give Caution. Missing essential checks never default to Low Risk: Low Risk requires adequate input, usable script coverage, fully grounded available AI and all embedded URL checks Low Risk.

English rules and targeted Hindi/Telugu requests, negations and mixed-language inputs are tested. This is not comprehensive linguistic support. Other scripts are flagged unsupported/uncertain. Regex clause/quote context can miss subtle sarcasm, attribution or indirect requests; full real Qwen quality and multilingual coverage remain unverified. Structured output and exact quotation grounding constrain AI output but do not prove the correctness of an interpretation. External-claim filtering is an additional heuristic, not factual verification.

The real provider-approved malicious fixture is not verified without a Web Risk key. Controlled unit tests check policy for a listed URL, while the live provider tests explicitly skip rather than invent a result. Model failures remain visible; later Qwen success needs a real run on suitable hardware.

## Validation

```bash
.venv/bin/python -m pytest tests/test_message.py tests/test_message_api.py tests/test_link.py tests/test_link_api.py -q
npm run build
```

Final result: **70 passed, 2 skipped** (both live Web Risk tests require the missing key), and Vite production build passed. Tests include ordinary conversation, OTP disclosure, safety warnings, advance-fee jobs, every distinct embedded URL, an authoritative listed fixture, educational/quoted contexts, Hindi/Telugu/mixed messages, unsupported script, empty/short text, prompt injection, Unicode offsets, limits, schema retries, hallucinated quote rejection, missing model, model context budget and private history/session ownership. Mock model/provider responses are used only in isolated tests, never in the application.
