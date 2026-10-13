# Media Check — real extraction, honest authenticity limits

Implemented 14 October 2026. Media Check uploads the actual file, validates content/codecs, extracts real frames/audio, uses local PaddleOCR and Whisper, reuses Message/Link analysis, and renders exact timestamps with the original media preview. No fabricated authenticity percentages, transcripts or scores are returned.

## Files and tools

Created `backend/app/services/media_worker.py`, `backend/app/services/media_jobs.py`, `backend/app/routers/media.py`, `requirements-media.txt`, `scripts/create_media_fixtures.py`, `scripts/verify_media.py`, `tests/test_media_offer.py` and reports. Replaced `backend/app/services/media_service.py`; updated `main.js`, API registration/lifespans, upload middleware, legacy assessment handling, minimal history metadata and fixture ignore rules. Offer changes share the same frontend controls and services.

Existing installed tools used, without new model downloads: FFmpeg/FFprobe 9.0.2, OpenAI Whisper 20250625, PyTorch 2.14.1, Pillow, PaddleOCR 3.7.0/PaddlePaddle 3.3.1 and cached multilingual Whisper `tiny.pt`. Whisper checkpoint SHA-256 is validated against the official package's model registry before loading. Whisper runs in a temporary, killable CPU worker with one Torch/BLAS thread; it transcribes rather than translating. [Official Whisper source](https://github.com/openai/whisper) and [model card](https://github.com/openai/whisper/blob/main/model-card.md) describe speech recognition and its limits; it is not voice-clone or identity detection.

## Decoding, limits and timestamps

Supported content: single-frame PNG/JPEG/WEBP; MP4/MOV/WEBM; WAV/MP3/M4A/AAC, subject to installed FFmpeg decoders. Codec allowlist: H.264, HEVC, VP8, VP9, AV1, MPEG-4 video; AAC, MP3, Opus, Vorbis and supported PCM audio. AVI and unrelated containers/codecs are unsupported. Filenames cannot establish type. Corrupt, unsupported and over-limit files do not receive a Low Risk fallback.

Uploads: 50 MiB. Video/audio: positive duration through 120 seconds, at most one video and one audio stream. Video: at most 4096 pixels/side, 8,294,400 input pixels and 120 fps. Images: at most 6000 pixels/side and 12 million pixels. Images are validated/decoded inside the worker, with bounded OCR working images fitted inside 1600×1600 and polygons tied to those working dimensions; original dimensions and preview are preserved, with EXIF orientation applied and actual selected camera/software metadata disclosed as observations.

FFprobe obtains only actual selected fields: container, duration/start time, codecs, dimensions, frame rate, audio/video streams, creation/encoder tags where present. FFmpeg uses fixed argument arrays, no shell, local `file,pipe` protocol allowlist, one decoder/filter thread, a 64 MiB individual allocation limit and bounded subprocess deadlines. A private temporary directory holds the upload, sampled PNGs, extracted WAV and bounded JSON. Cancellation kills the worker process group, including active decoders. This is bounded process isolation, not a complete OS sandbox or a total memory guarantee; CPU time is capped at 120 seconds per worker, decode parent deadline 100 seconds and transcription parent deadline 150 seconds. Full jobs have a 600-second deadline and are serialized.

Sampling: beginning, midpoint and last-frame interval calculated from actual video duration and frame rate, maximum three samples. Frames preserve actual decoded presentation timestamps relative to the container timeline. Absolute frame numbers are null when unavailable. Frames are scaled to maximum width 1280 for OCR. The original browser video remains unchanged. No scene-change or whole-video visual analysis is claimed. Identical decoded PNG hashes may reuse an actual OCR result within the same job; reuse is disclosed and `actual_ocr_executions` differs from samples when appropriate.

Audio extraction is actual 16 kHz mono PCM WAV, limited to the first 60 seconds. Actual audio start offset is preserved; transcript segments retain both WAV-relative and original-media timestamps. A measured RMS silence threshold avoids hallucinated transcription of digital silence; this does not prove that quiet speech is absent. Whisper segment text, start/end, log probability and no-speech observations are actual outputs. Uncertain recognition is disclosed and cannot produce a strong credential verdict or contact uncertain spoken URLs. Quoted/educational and prompt-injection speech remain content only.

OCR reuses Screenshot Check's real PaddleOCR, region/polygon/confidence handling and grounded Message/Link results. Speech segments reuse existing Message Check; recognized URLs reuse protected Link Check. Timestamp buttons seek the locally uploaded original video/audio to the actual finding segment/sample. Transcription, OCR and metadata are distinct from authenticity.

## Jobs, privacy and frontend

Uses the existing persisted `JobModel` for queued, processing, completed, failed and cancelled states. `POST /api/check/media?stream=true` sends real stages over NDJSON; `queued=true` returns a job ID immediately. Session-owned `GET /api/jobs/{id}`, result and cancellation endpoints are available. Other sessions receive 404. Interrupted jobs are marked failed on startup; cancellation stops processing and cleanup. Full result data remains transient in API memory for up to 15 minutes for the job result endpoint, and is cleared on shutdown. Persistent assessment/job records contain minimal metadata/stages and no media, transcript, OCR or detailed result content.

Uploaded files, extracted frames/audio and intermediates are removed after completion/cancellation. Browser previews are local blob URLs; the browser retains only active input/result memory and revokes replaced preview URLs. No raw media or transcripts are logged by application workers. Details are not recovered from metadata-only history after refresh. Existing UI layout/theme preserved. Upload/change, original preview, timestamp seek, Back, real retry/cancel, remove and reset were exercised. Check Another and Evidence/Checks use the same existing controls; native drag/drop was not separately exercised.

## GPU and specialist detector status

Hardware inspected: Apple M2 MacBook Air, 8-core integrated GPU, 16 GB unified system memory. GPU available: **yes, Metal**. NVIDIA/CUDA available: **no**. Dedicated VRAM: **none**; the GPU shares system RAM. Ollama reported an approximately 11.8 GiB Metal working-set budget, which is not dedicated VRAM.

Configured detector: **none**. Candidate reviewed: DeepfakeBench **Xception**, not installed or downloaded. Missing: a provenance/licence-verified `training/weights/xception_best.pth`, compatible runtime, face/landmark preprocessing resources and representative held-out evaluation. Its [configuration](https://raw.githubusercontent.com/sever46/DeepfakeBench/main/training/config/detector/xception.yaml) uses face-oriented data, 256-pixel inputs, normalization mean/std 0.5 and CUDA by default; its train dataset is FaceForensics++, with FaceForensics++/DeepFakeDetection test configuration. [Preprocessing](https://raw.githubusercontent.com/sever46/DeepfakeBench/main/preprocessing/preprocess.py) includes face alignment/cropping and landmark resources. MPS/CPU integration and performance have not been established here; no minimum VRAM figure is invented.

The [DeepfakeBench repository](https://github.com/sever46/DeepfakeBench) is a framework under CC BY-NC 4.0; checkpoint/data terms require separate verification. No commercial deployment licence is inferred. Candidate scope is face manipulation in suitable faces, not landscapes, all synthetic artwork or cloned audio. No face detector ran, so no fabricated “face detected/not detected” claim is returned. A manipulation score, probability or threshold is never substituted.

Measured local detector precision/recall/AUC/FPR/FNR/EER: **not measured**. No calibrated output. Legal held-out face-manipulated/genuine comparison data were not acquired/evaluated because no detector is configured. Results clearly state **Deepfake authenticity analysis unavailable** and **Audio authenticity detection unavailable**. This capability remains unfinished until the missing model/runtime/evaluation is supplied.

## Real end-to-end verification

Full real API results: [media-verification.json](media-verification.json). Browser results: [media-browser-verification.json](media-browser-verification.json). Controlled speech uses local macOS TTS, explicitly synthetic test input; these clips evaluate extraction/transcription, not deepfake detection.

Browser uploaded `otp.mp4`: validated video/MP4-family container; 109,848 bytes; SHA-256 `dfd9c84f59a3e29b3f4a0bed0bbe3620440a2e81f4e3d306401e1135dd36bf2f`; duration 8.343813 seconds. Final sampled timestamps **0.00, 4.20, 8.00 seconds**. Actual frames contained five OCR regions including `Send me your OTP` and `https://example.com`. Actual extracted WAV duration was 8.3438125 seconds. Whisper `tiny` returned two actual segments (0–6.96 and 6.96–8.28 seconds), including `send me your one-time password` and a payment request. Message/Link reuse produced exact source/timestamp evidence, real DNS/RDAP/HEAD checks and unavailable reputation (no key). Final content **High Risk**; authenticity **Unable to Assess**. Assessment `asmt_a10385d3c372` reached the frontend with the original clip; seeking 4.20 seconds was verified against the player's actual `currentTime`.

Changing to `silent.mp4` (different hash, 1,903 bytes, two-second duration, no audio) generated `asmt_3e4230066f19`, with actual frames 0, 1, 1.8 seconds and no recognized content. Both content/authenticity remained Unable to Assess. Identical silent frames reused one actual OCR run, explicitly disclosed. Retry initiated another real job; cancellation stopped it, then remove/reset cleared the input/result.

18 serialized actual API uploads tested ordinary image, text/URL image, ordinary speech video, OTP/payment video, no-audio/silent video, very short video, over-duration video, unsupported codec/container, corrupt video, Hindi/Telugu/mixed speech, MP3/M4A audio-only files, compressed/re-encoded video, injection speech and WEBM/MOV containers. The initial sampler missed some end intervals; the final sampler was corrected and verified with real decoded end timestamps in the browser and regression test. Initial test responses are retained honestly, rather than overwritten as though every sample succeeded.

English speech was understandable but not exact (for example “today” became “to date”). Hindi/Telugu recognition was poor; mixed speech omitted later languages. These are **not reliable supported transcription languages** on this tiny model. The final policy labels non-English/mixed transcription uncertain and does not contact URLs based on it. OCR language support retains the Screenshot module's documented limits. Improving language accuracy requires a suitably evaluated model/hardware; none was automatically downloaded.

## Startup

```bash
cd '/Users/thrishalyeggoni/Documents/New project/Safe-Lens-AI'
uv pip install --python .venv/bin/python -r requirements-media.txt
MESSAGE_AI_ENABLED=false .venv/bin/python -m uvicorn backend.app.link_main:app --host 127.0.0.1 --port 8000
```

Separate terminal in the same directory:

```bash
npm run dev -- --host 127.0.0.1
```

FFmpeg/FFprobe must be on PATH (`brew install ffmpeg` if missing). Whisper tiny must already be provisioned in `~/.cache/whisper/tiny.pt`; uploads never download it. Screenshot OCR models use the existing explicit setup script. Ctrl+C stops the API and jobs; short-lived workers exit after processing. No new persistent model service or specialist detector was installed.

Validation: full regression suite 161 passed, 2 external-provider checks skipped; after final model/boundary changes, the affected suites passed 69 tests with 1 external-provider skip. Production build, package compatibility and whitespace checks passed. A direct real worker check confirmed transparent-image compositing, then exited. No guarantee of general model accuracy is inferred.

Final shutdown: no API/model listeners on ports 8000, 8001 or 11434 and no remaining FFmpeg/media/OCR/document/ClamAV/model processing workers. The auto-restarting Homebrew Ollama service was stopped as requested for laptop heat. Frontend left running.
