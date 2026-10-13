# Real Link Check

The existing Link Check panel submits the entered URL to `POST /api/check/link`. JSON requests use `{ "url": "https://example.com" }`. The panel requests `?stream=true` and consumes newline-delimited JSON stage events emitted by the actual backend pipeline. There are no Link Check sample verdicts, numeric risk scores, artificial percentages, fabricated DNS/RDAP records, or AI interpretations.

## Run locally

From the repository directory:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-link.txt
.venv/bin/python -m uvicorn backend.app.link_main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/#/check/link`. Stop the API with Ctrl+C. The lightweight API imports no Torch, media services, OCR engines, or Ollama components. It supports Link Check, session history, and stored assessment retrieval. Other real module endpoints require the full backend (`backend.app.main:app`); their existing clearly labeled demos remain separate.

The project environment already contained all required runtime packages from the earlier install. No additional package installation was necessary for this change. `requirements-link.txt` declares FastAPI, Uvicorn, Pydantic, pydantic-settings, SQLAlchemy, httpx, dnspython, tldextract, idna, and python-dotenv. Development tests additionally use pytest and pytest-asyncio, already installed. The full `requirements.txt` now explicitly declares idna and bounds httpx below version 1.

## Web Risk setup required from the owner

1. Select/create a Google Cloud project and enable the Web Risk API, completing any billing setup required by Google.
2. Create an API key restricted to Web Risk; apply appropriate server/IP restrictions for your deployment.
3. Create/edit the ignored repository-root `.env` locally and set `GOOGLE_WEB_RISK_API_KEY=your_key`. `.env.example` contains an empty placeholder. Do not put the key in frontend code, commit it, or paste it into chat.
4. Restart the backend. The settings object loads environment values / `.env` at process startup.
5. Run the provider-approved live test described below.

The key is sent only from the backend in `X-Goog-Api-Key`, never in client assets or provider query strings. No key means reputation is explicitly unavailable. A failed request, malformed response, timeout, or quota error also remains unavailable. A successful empty threat response is displayed as **Not listed by this reputation provider**. This is not a safety guarantee.

Official references: [Google Web Risk Lookup](https://docs.cloud.google.com/web-risk/docs/lookup-api), [Google Web Risk setup](https://docs.cloud.google.com/web-risk/docs/setup), [IANA RDAP bootstrap](https://data.iana.org/rdap/dns.json), [HTTPX SNI extension](https://www.python-httpx.org/advanced/extensions/#sni_hostname).

## Risk policy

- **High Risk:** at least one actual Google Web Risk threat match on the input or an inspected redirect URL. Weak indicators alone never produce High Risk.
- **Caution:** at least one explainable URL/redirect structural indicator, with missing services still disclosed. IP hostnames, IDN usage, familiar names in subdomains, shorteners, unusual ports, long hostnames, excessive subdomains, many hyphens, embedded credentials, HTTP, and multiple redirects are weak indicators, not proof of maliciousness.
- **Low Risk:** DNS resolves only to public addresses, RDAP successfully identifies the requested registered domain, all performed reputation lookups return a non-match, redirect inspection finishes with a successful HTTP status, and no significant structural indicators occur. Always accompanied by the limitation that automated checks cannot guarantee safety. HTTPS alone cannot produce Low Risk.
- **Unable to Assess:** a destination was blocked as non-public, or required evidence is missing/inconclusive and no meaningful structural warning permits a Caution classification.

Registration age is derived only from a valid returned RDAP registration timestamp. A young domain is recorded as a weak indicator, and does not independently change the verdict. IP hosts have no domain RDAP registration lookup. Missing creation/expiry dates and registrar are null or absent, never invented.

## Request safety and limits

Only HTTP/HTTPS URLs are normalized. Internationalized hosts are canonicalized with idna UTS46/STD3 rules. Fragments and credentials are removed; embedded credentials are reported as a warning and never transmitted. tldextract uses its bundled Public Suffix List including private suffixes; it does not fetch a list during URL parsing.

A and AAAA records are queried with dnspython using the system-configured resolver. Every returned address must be globally routable. Loopback, private, link-local, reserved, multicast, metadata addresses, local hostname suffixes, mapped IPv6, and transition addresses are blocked. Partial DNS failures fail closed.

Each redirect is resolved and validated afresh. The HTTP connection targets the validated literal IP, preserving the original Host header and TLS SNI/certificate identity. This closes the DNS validation-to-connection rebinding gap. Environment proxies are disabled. TLS verification remains enabled. Only ports 80 and 443 are inspected. Redirect credentials, loops, malformed destinations, and excessive hops stop inspection.

Target inspection uses HEAD only, at most four redirects/five requests, with a 3-second HTTP timeout and a 15-second total redirect budget. No target body is consumed, no GET fallback is used, and JavaScript is never executed. Servers that reject HEAD or return non-success terminal statuses are explicitly inconclusive. RDAP/IANA JSON retrieval is separately validated/pinned, bounded to 1 MiB per response and 12 seconds per lookup, and supports at most three redirects. Web Risk responses are bounded to 64 KiB and six seconds. Provider failures are reported without serializing secret-bearing request objects.

URL checks contact the target, DNS resolver, registry RDAP service, and configured reputation provider. The entire normalized URL, including its query, is sent to Google Web Risk when configured. Do not submit links containing private tokens unless sharing that URL with the provider is intended. SQLite history is local to the backend and scoped to the visitor's HTTP-only session cookie.

## Field provenance

| Returned fields | Actual source/tool |
| --- | --- |
| `normalized_url`, `hostname`, canonical IDN | urllib.parse, idna; original input |
| `registered_domain` | tldextract bundled Public Suffix List |
| `dns.addresses`, `dns.records`, errors | dnspython A/AAAA answers; Python ipaddress for literal IPs and public-range validation |
| RDAP registration date, expiry, registrar, nameservers, statuses | Official registry RDAP selected through the IANA bootstrap; absent when not returned |
| `rdap.age_days` | UTC age calculated from the returned RDAP registration date |
| reputation status, threat types, expiry, HTTP error | Google Web Risk `uris:search`; missing key clearly reported as unavailable |
| redirect sources, HTTP statuses, destinations, errors | Actual pinned-IP, TLS-verified httpx HEAD responses; validation errors are reported separately |
| heuristic findings | Documented deterministic rules applied to observed URL structure / redirect count / returned RDAP age |
| category, explanation, recommendations | Documented SafeLens deterministic policy; no AI facts or interpretations |
| lookup/check timestamps | Backend UTC clock, ISO 8601 |
| id, history, created time, retention expiry | Local SQLAlchemy/SQLite persistence and backend clock |
| performed/unavailable checks | Actual per-service completion state, including failures and blocked requests |

All observations carry provider labels and lookup times; RDAP and reputation include their source endpoints. The frontend offers the exact backend JSON along with separate DNS, RDAP, reputation, redirect, evidence, and safeguard sections.

## Files created/modified in this implementation

Created:

- `backend/app/services/url_normalizer.py`
- `backend/app/services/dns_service.py`
- `backend/app/services/rdap_service.py`
- `backend/app/services/reputation_service.py`
- `backend/app/services/redirect_service.py`
- `backend/app/routers/link.py`
- `backend/app/link_main.py`
- `requirements-link.txt`, `.env.example`
- `tests/test_link_api.py`, `docs/link-check.md`

Modified:

- `backend/app/services/url_service.py`: real pipeline, explicit evidence policy, no numeric score
- `backend/app/config.py`: backend Web Risk key setting
- `backend/app/main.py`: register new endpoint in full runtime
- `backend/app/database.py`: persist/retrieve full link observations and UTC timestamps
- `backend/app/routers/assessments.py`: legacy endpoint validation errors
- `main.js`, `style.css`: live endpoint/progress, actual failures, exact results, remove Link Check demo flow
- `requirements.txt`: explicit idna / httpx version boundary
- `tests/test_link.py`: meaningful security/provider/policy coverage
- `README.md`: Link Check instructions

Prior cursor and module-image changes remain in the working tree.

## Verification

```sh
.venv/bin/python -m pytest tests/test_link.py tests/test_link_api.py -q
npm run build
```

Tests cover malformed input, private/localhost/metadata/IPv6 destinations, mixed public/private DNS answers, NXDOMAIN, redirects to private addresses, DNS rebinding, literal-IP connection pinning with TLS hostname preservation, redirect bounds, IDN and IP indicators, missing RDAP, missing Web Risk configuration, actual API errors and streaming stage events, exact persisted results, and session isolation. Provider response tests use deterministic fixtures strictly in tests.

The live provider-approved test uses `http://testsafebrowsing.appspot.com/s/malware.html`, the Google Lookup documentation's test URI. It calls the provider only and never loads the unsafe page. It is skipped when `GOOGLE_WEB_RISK_API_KEY` is absent; the provider integration must not be reported as live-verified in that state.

A real public-URL browser test and its observed fields are recorded in the completion report. Runtime data changes between requests; the verification result is evidence of a particular request, not a seeded runtime result.

## Completion evidence (13 October 2026)

The browser submitted `https://example.com`, then `https://example.org`, through the live streaming endpoint. Each request produced fresh DNS/RDAP/HTTP observations and a different assessment id. For `https://example.org/`, A and AAAA records resolved to public addresses, RDAP returned the real registration date `1995-08-31T04:00:00Z` from `https://rdap.publicinterestregistry.org/rdap/domain/example.org`, and a TLS-verified HEAD request returned HTTP 200 with zero redirects. Web Risk reported `unavailable` because the API key was absent; the verdict was therefore `Unable to Assess`, with no numeric score.

The browser's exact-result JSON was compared against the persisted backend result with full object equality, including all observations and timestamps. See [the actual verification response](link-check-verification.json). This JSON is a captured verification artifact, not an input to the running website.

Validation: 41 tests passed; one live Web Risk test skipped because credentials are missing. The frontend production build and Git whitespace check passed. Import inspection confirmed the lightweight API loads neither Torch nor the Ollama service. The test API process was stopped after verification; no backend listener remains on port 8000. The existing frontend preview remains available.

Remaining capability: an authenticated live Web Risk lookup (including the provider-approved unsafe-URL test) cannot be verified until the owner enables Web Risk and supplies `GOOGLE_WEB_RISK_API_KEY` locally. No credential was generated or fabricated.
