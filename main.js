import { summarizeResult, plainSignal } from './result-summary.js';

/* ==========================================================================
   SAFELENS AI — INTERACTIVE CANVAS & EXPERIENCE ENGINE
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  initCustomCursor();
  initCheckDropdown();
  initHeroCanvasSequence();
  initCrazyMode();
  initLanguageDropdown();
  initCardsInteractions();
  initModalInteractions();
  initEvidenceTabs();
  initRouter();
  loadDashboardData();
});

/* --------------------------------------------------------------------------
   1. CUSTOM CURSOR (SYNCHRONIZED DOT AND RING)
   -------------------------------------------------------------------------- */
function initCustomCursor() {
  const cursor = document.getElementById('customCursor');
  const follower = document.getElementById('cursorFollower');
  if (!cursor || !follower) return;

  let isVisible = false;

  window.addEventListener('pointermove', (e) => {
    if (e.pointerType === 'touch') { hideCursor(); return; }

    // Both layers use the same coordinates in the same event, without easing.
    const position = `translate3d(${e.clientX}px, ${e.clientY}px, 0) translate(-50%, -50%)`;
    cursor.style.transform = position;
    follower.style.transform = position;

    if (!isVisible) {
      isVisible = true;
      cursor.style.opacity = '1';
      follower.style.opacity = '1';
      document.body.classList.add('custom-cursor-active');
    }

    // Detect if cursor is over a light / white container
    const target = e.target;
    if (target) {
      const isLight = !!target.closest(
        '.hero-card-container, .threat-service-card, .process-card, .evidence-card-shell, .dashboard-card, .assessment-breakdown-card, .recent-assessments-card, .session-telemetry-card, .rule-of-thumb-card'
      ) && !target.closest('.nav-notch-left, .nav-notch-right, .hero-bottom-notch, .hud-readout, .threat-icon-box');

      if (isLight) {
        document.body.classList.add('cursor-on-light');
      } else {
        document.body.classList.remove('cursor-on-light');
      }
    }
  }, { passive: true });

  function hideCursor() {
    cursor.style.opacity = '0';
    follower.style.opacity = '0';
    isVisible = false;
    document.body.classList.remove('custom-cursor-active');
  }
  document.documentElement.addEventListener('pointerleave', hideCursor);
  window.addEventListener('blur', hideCursor);

  // Hover expansion over interactive elements
  const interactives = document.querySelectorAll(
    'a, button, input, .partner-card, .stepped-tab-card, .toggle-opt, .threat-item, .threat-service-card, .process-card, .assessment-item'
  );
  interactives.forEach((el) => {
    el.addEventListener('mouseenter', () => document.body.classList.add('cursor-hover'));
    el.addEventListener('mouseleave', () => document.body.classList.remove('cursor-hover'));
  });
}

/* --------------------------------------------------------------------------
   2. CHECK DROPDOWN (SEVEN THREAT MODULES)
   -------------------------------------------------------------------------- */
function initCheckDropdown() {
  const dropdownItem = document.getElementById('checkDropdownItem');
  const dropdownBtn = document.getElementById('checkDropdownBtn');
  const menu = document.getElementById('threatModulesMenu');
  if (!dropdownItem || !dropdownBtn || !menu) return;

  function toggleDropdown(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    const isOpen = dropdownItem.classList.toggle('open');
    dropdownBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }

  function closeDropdown() {
    dropdownItem.classList.remove('open');
    dropdownBtn.setAttribute('aria-expanded', 'false');
  }

  dropdownBtn.addEventListener('click', toggleDropdown);

  // Close when clicking outside
  document.addEventListener('click', (e) => {
    if (!dropdownItem.contains(e.target)) {
      closeDropdown();
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeDropdown();
    }
  });

  // Close when clicking any menu threat item
  const threatItems = menu.querySelectorAll('.threat-item');
  threatItems.forEach((item) => {
    item.addEventListener('click', () => {
      closeDropdown();
    });
  });
}

/* --------------------------------------------------------------------------
   3. HERO 3D SEQUENCE CANVAS CONTROLLER (4K HIDPI QUALITY)
   -------------------------------------------------------------------------- */
function initHeroCanvasSequence() {
  const canvas = document.getElementById('heroCanvas');
  const container = document.getElementById('heroCanvasContainer');
  const replayBtn = document.getElementById('btnReplayIntro');
  if (!canvas || !container) return;

  const ctx = canvas.getContext('2d');
  const TOTAL_FRAMES = 65;
  const frames = [];
  let loadedCount = 0;
  let isReady = false;

  // Frame animation state
  let currentFrameFloat = 1.0;
  let targetFrame = 1.0;
  let isMouseOver = false;
  let lastMouseMoveTime = Date.now();
  let isDragging = false;
  let startDragX = 0;
  let startDragFrame = 1;
  let isReplaying = false;

  // 4K HiDPI Canvas setup
  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    drawFrame(Math.round(currentFrameFloat));
  }

  // Preload all 65 remastered 4K frames with progressive instant display
  for (let i = 1; i <= TOTAL_FRAMES; i++) {
    const img = new Image();
    const pad = String(i).padStart(3, '0');
    img.src = `/hero-sequence/frame_${pad}.webp`;
    img.onload = () => {
      loadedCount++;
      // Render immediately on first frame load
      if (i === 1) {
        isReady = true;
        drawFrame(1);
      }
      if (loadedCount === TOTAL_FRAMES) {
        isReady = true;
      }
    };
    frames.push(img);
  }

  function drawFrame(frameIdx) {
    const idx = Math.max(1, Math.min(TOTAL_FRAMES, Math.round(frameIdx)));
    const targetImg = frames[idx - 1];
    const img = (targetImg && targetImg.complete && targetImg.naturalWidth > 0)
      ? targetImg
      : (frames[0] && frames[0].complete && frames[0].naturalWidth > 0 ? frames[0] : null);

    if (!img) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Calculate aspect fit with centered high-precision bounds
    const scale = Math.min(canvas.width / img.width, canvas.height / img.height);
    const renderW = Math.round(img.width * scale);
    const renderH = Math.round(img.height * scale);
    const x = Math.round((canvas.width - renderW) / 2);
    const y = Math.round((canvas.height - renderH) / 2);

    ctx.drawImage(img, x, y, renderW, renderH);

    // If crazy mode is on, draw digital aberration tint
    if (window.__isCrazyMode) {
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      ctx.globalAlpha = 0.18;
      ctx.drawImage(img, x + 5, y, renderW, renderH);
      ctx.restore();
    }
  }

  // Replay intro feature
  if (replayBtn) {
    replayBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (!isReady) return;
      isReplaying = true;
      currentFrameFloat = 1.0;
      targetFrame = 1.0;

      // Animate from frame 1 through 65 and settle at frame 35
      const startTime = performance.now();
      const duration = 1800; // 1.8s intro sweep

      function runReplay(now) {
        const elapsed = now - startTime;
        const progress = Math.min(1, elapsed / duration);
        // Eased progress
        const ease = progress < 0.5
          ? 2 * progress * progress
          : 1 - Math.pow(-2 * progress + 2, 2) / 2;

        if (progress < 1) {
          currentFrameFloat = 1 + ease * (TOTAL_FRAMES - 1);
          drawFrame(currentFrameFloat);
          requestAnimationFrame(runReplay);
        } else {
          isReplaying = false;
          targetFrame = 35;
          lastMouseMoveTime = Date.now();
        }
      }
      requestAnimationFrame(runReplay);
    });
  }

  // Mouse & Scrub tracking
  window.addEventListener('mousemove', (e) => {
    if (window.__isCrazyMode || isReplaying) return;
    const rect = container.getBoundingClientRect();

    // Check if within proximity to hero
    if (e.clientY >= 0 && e.clientY <= rect.bottom + 200) {
      isMouseOver = true;
      lastMouseMoveTime = Date.now();

      // Map mouse X relative to window into frame 1..65
      const normX = Math.max(0, Math.min(1, e.clientX / window.innerWidth));
      targetFrame = 1 + normX * (TOTAL_FRAMES - 1);
    } else {
      isMouseOver = false;
    }
  });

  // Touch and drag support directly on canvas
  canvas.addEventListener('mousedown', (e) => {
    if (isReplaying) return;
    isDragging = true;
    startDragX = e.clientX;
    startDragFrame = currentFrameFloat;
  });

  window.addEventListener('mouseup', () => { isDragging = false; });

  window.addEventListener('mousemove', (e) => {
    if (!isDragging || isReplaying) return;
    const dx = e.clientX - startDragX;
    const frameDelta = (dx / 320) * TOTAL_FRAMES;
    targetFrame = Math.max(1, Math.min(TOTAL_FRAMES, startDragFrame + frameDelta));
    lastMouseMoveTime = Date.now();
  });

  // Main Render Loop
  let idleTime = 0;
  function animateSequence() {
    if (isReady && !isReplaying) {
      const now = Date.now();

      if (window.__isCrazyMode) {
        // High speed spin in crazy mode
        currentFrameFloat = (currentFrameFloat + 1.25) % TOTAL_FRAMES;
        if (currentFrameFloat < 1) currentFrameFloat = 1;
        drawFrame(currentFrameFloat);
      } else {
        // Organic sine float oscillating gently when idle
        if (!isDragging && (!isMouseOver || now - lastMouseMoveTime > 2200)) {
          idleTime += 0.025;
          targetFrame = 35 + Math.sin(idleTime) * 9;
        }

        // Smooth physics-based lerp to target frame
        currentFrameFloat += (targetFrame - currentFrameFloat) * 0.12;
        drawFrame(currentFrameFloat);
      }
    }
    requestAnimationFrame(animateSequence);
  }

  window.addEventListener('resize', resizeCanvas);
  resizeCanvas();
  requestAnimationFrame(animateSequence);
}

/* --------------------------------------------------------------------------
   4. CRAZY MODE ENGINE & SYNTHESIZER
   -------------------------------------------------------------------------- */
function initCrazyMode() {
  const onBtn = document.getElementById('crazyOn');
  const offBtn = document.getElementById('crazyOff');
  const heroContainer = document.getElementById('heroSection');
  if (!onBtn || !offBtn || !heroContainer) return;
  window.__isCrazyMode = false;

  function playCyberSound(isActivation) {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc.type = isActivation ? 'sawtooth' : 'sine';
      const startFreq = isActivation ? 220 : 660;
      const endFreq = isActivation ? 880 : 220;

      osc.frequency.setValueAtTime(startFreq, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(endFreq, audioCtx.currentTime + 0.3);

      gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
      gain.gain.linearRampToValueAtTime(0.001, audioCtx.currentTime + 0.3);

      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.3);
    } catch (e) {
      // Silent fallback
    }
  }

  function setCrazyMode(state) {
    window.__isCrazyMode = state;
    if (state) {
      onBtn.classList.add('active');
      offBtn.classList.remove('active');
      heroContainer.classList.add('crazy-mode-active');
      playCyberSound(true);
    } else {
      offBtn.classList.add('active');
      onBtn.classList.remove('active');
      heroContainer.classList.remove('crazy-mode-active');
      playCyberSound(false);
    }
  }

  onBtn.addEventListener('click', () => setCrazyMode(true));
  offBtn.addEventListener('click', () => setCrazyMode(false));
}

/* --------------------------------------------------------------------------
   5. LANGUAGE SELECTOR
   -------------------------------------------------------------------------- */
function initLanguageDropdown() {
  const dropdown = document.querySelector('.lang-selector-dropdown');
  const btn = document.getElementById('langBtn');
  const options = document.querySelectorAll('.lang-option');
  if (!dropdown || !btn) return;

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('open');
  });

  options.forEach((opt) => {
    opt.addEventListener('click', () => {
      options.forEach(o => o.classList.remove('active'));
      opt.classList.add('active');
      btn.querySelector('span').textContent = opt.textContent;
      dropdown.classList.remove('open');
    });
  });

  window.addEventListener('click', () => {
    dropdown.classList.remove('open');
  });
}

/* --------------------------------------------------------------------------
   6. REAL-BACKEND INTAKE & THREAT CARDS
   -------------------------------------------------------------------------- */
let activeModule = 'link';
let activeSelectedFile = null;
let activeAbortController = null;
let currentAssessment = null;
let mediaFile = null, mediaResultId = null, mediaResultUrl = null;
let offerFile = null, offerText = '', offerResultId = null;
let documentFile = null;
let documentResultId = null;
let documentLanguage = 'en';
let qrFile = null;
let qrResultUrl = null;
let qrResultId = null;
let screenshotIntakeUrl = null;
let screenshotResultUrl = null;
let currentScreenshotFile = null;
let screenshotResultId = null;

const moduleExperiences = {
  link: { sheet: 'link-message', panel: 1, description: 'Look before you click. Inspect real DNS records, domain registration, configured reputation intelligence, and public redirect destinations.', signals: ['Domain · DNS & RDAP', 'Redirects · public destinations', 'Reputation · Google Web Risk'], action: 'Check link' },
  message: { sheet: 'link-message', panel: 2, description: 'Read between the lines. Analyse the exact message, review requests in context, and inspect any embedded links.', signals: ['Context · requests & warnings', 'Evidence · exact text spans', 'Links · real URL checks'], action: 'Analyse message' },
  screenshot: { sheet: 'link-message', panel: 0, description: 'See the hidden clues. Extract actual text and evidence boxes, inspect embedded links, and review requests in context.', signals: ['Local OCR · actual text & boxes', 'Links · real URL checks', 'Context · grounded message analysis'], action: 'Analyse screenshot' },
  qr: { sheet: 'link-message', panel: 1, description: 'Know where it leads. Decode actual QR images and review destinations and self-declared payment details.', signals: ['ZXing-C++ · actual QR payloads', 'URLs · existing Link Check', 'Payment · unverified parsed fields'], action: 'Analyse QR image' },
  document: { sheet: 'media-offer-review', panel: 2, description: 'Check the fine print. Parse actual pages, review malware scanning, and inspect links and exact evidence.', signals: ['PDF / DOCX · actual text and structure', 'Scanned pages · local PaddleOCR', 'ClamAV · separate malware scan'], action: 'Analyse document' },
  media: { sheet: 'media-offer-review', panel: 0, description: 'Look beyond the surface. Prepare your file, extract available signals, then review its source and context.', signals: ['Image signals · visual analysis', 'Video signals · frame analysis', 'Source check · origin & context'], action: 'Analyse media', sample: 'Illustrative video.mp4 · 12.4 MB', excerpt: 'No reliable source information is available for this sample.', warnings: ['Source not verified', 'Context unavailable', 'Authenticity inconclusive'], score: null },
  offer: { sheet: 'media-offer-review', panel: 1, description: 'Pause before the promise. Review guaranteed returns, advance fees, and pressure to pay.', signals: ['Offer claims · unverified promises', 'Advance fee · contextual requests', 'Pressure · exact evidence'], action: 'Analyse offer', sample: 'Guaranteed returns. Pay today. Limited time offer with high profits for everyone. Click the link to get started.', excerpt: 'Guaranteed returns. Pay today.', warnings: ['Guaranteed returns', 'Advance fee', 'Scam pattern'], score: 86 },
};

function updateModuleExperience() {
  const config = moduleExperiences[activeModule];
  const hero = document.getElementById('moduleExperience');
  hero.innerHTML = `<div class="module-reference-image" role="img" aria-label="${escapeHtml(activeModule)} check illustration" style="background-image:url('/assets/module-references/${config.sheet}.png');background-position:${config.panel * 50}% 20%"></div>
    ${activeModule === 'media' ? '<ol class="module-review-steps"><li>1 · Prepare</li><li>2 · Extract</li><li>3 · Review</li></ol>' : ''}
    <p class="module-explanation">${escapeHtml(config.description)}</p>`;
  document.getElementById('moduleSignals').innerHTML = config.signals.map(signal => `<div class="module-signal"><span class="module-signal-dot"></span>${escapeHtml(signal)}</div>`).join('');
  document.getElementById('submitBtnText').textContent = config.action;
  document.getElementById('btnModuleDemo').textContent = `Review ${activeModule} sample →`;
  document.querySelector('.module-demo-actions').hidden = ['link', 'message', 'screenshot', 'qr', 'document', 'media', 'offer'].includes(activeModule);
  document.getElementById('screenshotIntake').hidden = !['screenshot','qr','document','media','offer'].includes(activeModule);
  document.getElementById('screenshotLanguage').hidden = activeModule === 'qr';
  document.querySelector('label[for="screenshotLanguage"]').hidden = activeModule === 'qr';
  document.querySelector('#screenshotIntake .screenshot-note').hidden = activeModule === 'qr';
  document.getElementById('btnResetScreenshot').textContent = activeModule === 'qr' ? 'Reset QR image' : activeModule === 'document' ? 'Reset document' : activeModule === 'media' ? 'Reset media' : activeModule === 'offer' ? 'Reset offer' : 'Reset screenshot';
  document.querySelector('label[for="screenshotLanguage"]').textContent = activeModule === 'document' ? 'Scanned page language' : ['media','offer'].includes(activeModule) ? 'OCR / speech language' : 'Screenshot language';
  document.getElementById('screenshotInputPreview').hidden = ['document','media','offer'].includes(activeModule);
  document.getElementById('mediaIntakePreview')?.remove();
  document.getElementById('btnResetMessage').textContent=activeModule==='offer'?'Reset offer text':'Reset message';
  document.getElementById('messageInputActions').hidden = !['message','offer'].includes(activeModule);
  document.querySelector('label[for="inputTextField"]').textContent = activeModule === 'message' ? 'Message to review' : 'Message / Offer Body Text';
  document.getElementById('intakePrivacyNote').textContent = activeModule === 'link'
    ? 'The backend contacts DNS, registry RDAP, and the destination. When configured, Google Web Risk receives the normalized URL. History is stored locally.'
    : activeModule === 'message' ? 'Your text is processed by the backend and configured local model. Embedded URLs use Link Check. Only assessment metadata is saved; detailed results disappear on refresh.'
    : activeModule === 'screenshot' ? 'Local PaddleOCR processes your image temporarily. Readable URLs use Link Check; extracted text uses Message Check. Only metadata is saved. No cloud OCR is used.'
    : activeModule === 'qr' ? 'ZXing-C++ decodes your temporary image. URL payloads use Link Check. Credentials, payment identifiers and contact details are not stored. Nothing is opened or executed automatically.'
    : activeModule === 'document' ? 'Documents are parsed temporarily in isolated workers. Scanned pages use local OCR; URLs use Link Check. Only assessment metadata is saved. Scripts and attachments are not executed.'
    : 'Temporary local extraction and grounded content analysis. Authenticity and external claims are separate and may be unavailable. Only assessment metadata is saved.';
  document.getElementById('inputTextField').maxLength = ['message','offer'].includes(activeModule) ? 12000 : 500;
  updateMessageCount();
}

function updateMessageCount() {
  const field = document.getElementById('inputTextField');
  document.getElementById('messageCharacterCount').textContent = `${Array.from(field.value).length}/${field.maxLength}`;
}

function clearScreenshotInput(clearResult = false) {
  activeSelectedFile = null;
  document.getElementById('mediaIntakePreview')?.remove();
  if (activeModule==='offer' && clearResult) { document.getElementById('inputTextField').value=''; offerText=''; updateMessageCount(); }
  document.getElementById('fileUploadInput').value = '';
  document.getElementById('fileSelectedInfo').style.display = 'none';
  document.getElementById('dropzonePrompt').style.display = 'flex';
  const preview = document.getElementById('screenshotInputPreview');
  preview.hidden = true;
  preview.removeAttribute('src');
  if (screenshotIntakeUrl) URL.revokeObjectURL(screenshotIntakeUrl);
  screenshotIntakeUrl = null;
  if (clearResult && ['screenshot','qr','document','media','offer'].includes(currentAssessment?.module_type)) {
    mediaFile=null; mediaResultId=null; offerFile=null; offerResultId=null; offerText='';
    if(mediaResultUrl) URL.revokeObjectURL(mediaResultUrl); mediaResultUrl=null;
    documentFile = null; documentResultId = null;
    qrFile = null; qrResultId = null;
    if (qrResultUrl) URL.revokeObjectURL(qrResultUrl);
    qrResultUrl = null;
    currentAssessment = null;
    currentScreenshotFile = null;
    if (screenshotResultUrl) URL.revokeObjectURL(screenshotResultUrl);
    screenshotResultUrl = null;
    document.getElementById('evidenceActiveState').style.display = 'none';
    document.getElementById('assessmentOverview')?.replaceChildren();
    document.getElementById('findingsContainer').replaceChildren();
    document.getElementById('evidenceEmptyState').style.display = 'block';
  }
}

function showScreenshotPreview(file) {
  if (screenshotIntakeUrl) URL.revokeObjectURL(screenshotIntakeUrl);
  screenshotIntakeUrl = URL.createObjectURL(file);
  const preview = document.getElementById('screenshotInputPreview');
  preview.src = screenshotIntakeUrl;
  preview.hidden = false;
}

function reviewModuleSample() {
  if (['link', 'message', 'screenshot', 'qr', 'document', 'media', 'offer'].includes(activeModule)) return;
  const config = moduleExperiences[activeModule];
  const risk = config.score === null ? 'Unable to Assess' : 'High Risk';
  const actions = ['Do not share OTPs, passwords, or account details.', 'Avoid payment until you verify the request.', 'Verify the source through an official contact you find independently.', 'Learn common warning signs: urgency, guaranteed returns, and advance fees.'];
  const data = {
    id: `demo-${activeModule}`, demo: true, module_type: activeModule, created_at: new Date().toISOString(),
    input_summary: config.sample, risk_category: risk, demo_score: config.score,
    findings: config.warnings.map(warning => ({ source: 'Illustrative example', risk_level: config.score === null ? 'Caution' : risk, observation: warning, interpretation: 'Example warning sign for this module; this is not a finding about your submitted content.', action: actions[2] })),
    evidence: [{ source_type: 'Demo sample', snippet: config.excerpt, detail: 'Highlighted sample content — illustrative only.' }],
    checks_performed: [], unavailable_checks: config.signals.map(signal => ({ name: signal.split(' · ')[0], detail: 'Not run · demo mode' })), recommended_actions: actions,
  };
  document.getElementById('contactModal').classList.remove('open');
  renderAssessment(data);
  // The sample is already rendered; avoid a queued route change reopening it.
  window.history.replaceState(null, '', `#/results/${data.id}`);
  document.getElementById('architecture').scrollIntoView({ behavior: 'smooth' });
}

function setModalModule(moduleType) {
  activeModule = Object.hasOwn(moduleExperiences, moduleType) ? moduleType : 'link';

  // Update selector pills
  const pills = document.querySelectorAll('.module-pill-btn');
  pills.forEach((p) => {
    if (p.getAttribute('data-module') === activeModule) {
      p.classList.add('active');
    } else {
      p.classList.remove('active');
    }
  });

  const modalTitle = document.getElementById('assessmentModalTitle');
  const modalSub = document.getElementById('assessmentModalSub');
  const modalBadge = document.getElementById('modalBadgeText');
  const groupUrl = document.getElementById('groupUrlInput');
  const groupText = document.getElementById('groupTextInput');
  const groupFile = document.getElementById('groupFileInput');
  const urlInput = document.getElementById('inputUrlField');
  const textInput = document.getElementById('inputTextField');
  const fileLabel = document.getElementById('fileInputLabel');
  const fileInput = document.getElementById('fileUploadInput');
  const dropHint = document.getElementById('dropzoneHintText');

  if (modalBadge) modalBadge.textContent = `${activeModule.toUpperCase()} CHECK`;

  // Reset file selection
  activeSelectedFile = null;
  const fileInfo = document.getElementById('fileSelectedInfo');
  const dropPrompt = document.getElementById('dropzonePrompt');
  if (fileInfo) fileInfo.style.display = 'none';
  if (dropPrompt) dropPrompt.style.display = 'flex';
  if (fileInput) fileInput.value = '';

  switch (activeModule) {
    case 'link':
      if (modalTitle) modalTitle.textContent = 'Link Check — Look Before You Click';
      if (modalSub) modalSub.textContent = 'Real URL analysis with DNS, RDAP, protected redirects, and configured reputation checking. No AI or demo verdicts.';
      if (groupUrl) groupUrl.style.display = 'flex';
      if (groupText) groupText.style.display = 'none';
      if (groupFile) groupFile.style.display = 'none';
      if (urlInput) urlInput.placeholder = 'Enter the HTTP or HTTPS URL you want to check';
      break;

    case 'message':
      if (modalTitle) modalTitle.textContent = 'Message Check — Read Between the Lines';
      if (modalSub) modalSub.textContent = 'Actual message analysis with grounded evidence, real Link Check, and local Qwen interpretation when available.';
      if (groupUrl) groupUrl.style.display = 'none';
      if (groupText) groupText.style.display = 'flex';
      if (groupFile) groupFile.style.display = 'none';
      if (textInput) textInput.placeholder = 'Paste the full SMS, chat, email, or message you want to review';
      break;

    case 'screenshot':
      if (modalTitle) modalTitle.textContent = 'Screenshot Check — See Hidden Clues';
      if (modalSub) modalSub.textContent = 'Optical character recognition (OCR) and layout inspection for payment slips & lures.';
      if (groupUrl) groupUrl.style.display = 'none';
      if (groupText) groupText.style.display = 'none';
      if (groupFile) groupFile.style.display = 'flex';
      if (fileLabel) fileLabel.textContent = 'Screenshot / Image Upload (PNG, JPG, WEBP)';
      if (fileInput) fileInput.accept = '.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp';
      if (dropHint) dropHint.textContent = 'PNG, JPEG or WEBP · up to 10 MiB and 12 million pixels';
      break;

    case 'qr':
      if (modalTitle) modalTitle.textContent = 'QR Check — Know Where It Leads';
      if (modalSub) modalSub.textContent = 'Decode barcode matrices, inspect target URLs, and parse UPI payment identifiers.';
      if (groupUrl) groupUrl.style.display = 'none';
      if (groupText) groupText.style.display = 'none';
      if (groupFile) groupFile.style.display = 'flex';
      if (fileLabel) fileLabel.textContent = 'QR Code Image (PNG, JPEG, WEBP)';
      if (fileInput) fileInput.accept = '.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp';
      if (dropHint) dropHint.textContent = 'PNG, JPEG or WEBP · up to 10 MiB · one or multiple QR codes';
      break;

    case 'document':
      if (modalTitle) modalTitle.textContent = 'Document Check — Check the Fine Print';
      if (modalSub) modalSub.textContent = 'Deep PDF inspection: embedded launch actions, links, payment tables, and structure.';
      if (groupUrl) groupUrl.style.display = 'none';
      if (groupText) groupText.style.display = 'none';
      if (groupFile) groupFile.style.display = 'flex';
      if (fileLabel) fileLabel.textContent = 'PDF / DOCX Document';
      if (fileInput) fileInput.accept = '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      if (dropHint) dropHint.textContent = 'PDF / DOCX · up to 20 MiB · first 30 PDF pages · bounded scanned-page OCR';
      break;

    case 'media':
      if (modalTitle) modalTitle.textContent = 'Media Check — Look Beyond the Surface';
      if (modalSub) modalSub.textContent = 'Real metadata, bounded frame/audio extraction, local OCR and Whisper transcription. Authenticity detection is unavailable.';
      if (groupUrl) groupUrl.style.display = 'none';
      if (groupText) groupText.style.display = 'none';
      if (groupFile) groupFile.style.display = 'flex';
      if (fileLabel) fileLabel.textContent = 'Image, Video or Audio';
      if (fileInput) fileInput.accept = 'video/*,audio/*,image/*';
      if (dropHint) dropHint.textContent = 'PNG/JPEG/WEBP, MP4/MOV/WEBM, WAV/MP3/M4A/AAC · 50 MiB · 120 seconds maximum';
      break;

    case 'offer':
      if (modalTitle) modalTitle.textContent = 'Offer Check — Pause Before the Promise';
      if (modalSub) modalSub.textContent = 'Analyze job postings, tasks, and guaranteed return pitches for advance payment traps.';
      if (groupUrl) groupUrl.style.display = 'none';
      if (groupText) groupText.style.display = 'flex';
      if (groupFile) groupFile.style.display = 'flex';
      if (textInput) textInput.placeholder = 'Paste the actual job, shopping, investment or service offer, or upload one document separately';
      if (fileLabel) fileLabel.textContent = 'Optional Offer PDF / DOCX';
      if (fileInput) fileInput.accept = '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      if (dropHint) dropHint.textContent = 'Optional PDF / DOCX · 20 MiB · bounded real document extraction';
      break;
  }
  updateModuleExperience();
}

function initCardsInteractions() {
  const serviceCards = document.querySelectorAll('.stepped-threat-card');
  const modal = document.getElementById('contactModal');

  serviceCards.forEach((card) => {
    card.addEventListener('click', () => {
      const serviceType = card.getAttribute('data-service') || 'link';
      setModalModule(serviceType);
      modal.classList.add('open');
      window.location.hash = `#/check/${serviceType}`;
    });

    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        card.click();
      }
    });
  });
}

/* --------------------------------------------------------------------------
   7. MODAL & INTAKE INTERACTIONS
   -------------------------------------------------------------------------- */
async function readLinkCheckStream(response, onStage) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result = null;
  const consume = line => {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === 'stage') onStage(event.stage);
    if (event.type === 'error') throw new Error(event.detail);
    if (event.type === 'result') result = event.data;
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let end;
      while ((end = buffer.indexOf('\n')) >= 0) {
        consume(buffer.slice(0, end));
        buffer = buffer.slice(end + 1);
      }
      if (done) break;
    }
    consume(buffer);
  } finally {
    await reader.cancel();
  }
  if (!result) throw new Error('Backend connection ended before a result was returned.');
  return result;
}

function initModalInteractions() {
  document.getElementById('btnResetScreenshot').addEventListener('click', () => clearScreenshotInput(true));
  document.getElementById('btnResetMessage').addEventListener('click', () => {
    if(activeModule==='offer') { offerText='';offerFile=null;offerResultId=null; }
    document.getElementById('inputTextField').value = '';
    if (['message','offer'].includes(currentAssessment?.module_type)) {
      currentAssessment = null;
      document.getElementById('evidenceActiveState').style.display = 'none';
      document.getElementById('evidenceActiveState').querySelector('#assessmentOverview')?.replaceChildren();
      document.getElementById('findingsContainer').replaceChildren();
      document.getElementById('evidenceEmptyState').style.display = 'block';
    }
    updateMessageCount();
    document.getElementById('inputTextField').focus();
  });
  document.getElementById('btnModuleDemo').addEventListener('click', reviewModuleSample);
  document.getElementById('inputTextField').addEventListener('input', updateMessageCount);
  const modal = document.getElementById('contactModal');
  const closeBtn = document.getElementById('modalClose');
  const form = document.getElementById('assessmentForm');
  const fileDropzone = document.getElementById('fileDropzone');
  const fileUploadInput = document.getElementById('fileUploadInput');
  const fileSelectedInfo = document.getElementById('fileSelectedInfo');
  const selectedFileName = document.getElementById('selectedFileName');
  const btnRemoveFile = document.getElementById('btnRemoveFile');
  const dropzonePrompt = document.getElementById('dropzonePrompt');
  const btnCancelScan = document.getElementById('btnCancelScan');
  const modulePills = document.querySelectorAll('.module-pill-btn');

  // Trigger buttons
  const heroStartBtn = document.getElementById('heroStartCheckingBtn');
  const heroContact = document.getElementById('heroContactBtn');
  const btnConnect = document.getElementById('btnConnect');
  const footerConnect = document.getElementById('footerConnectBtn');
  const btnLaunchNewCheck = document.getElementById('btnLaunchNewCheck');

  function openModal(moduleType) {
    if (moduleType) setModalModule(moduleType);
    if (modal) modal.classList.add('open');
  }

  function closeModal() {
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }
    const overlay = document.getElementById('processingOverlay');
    if (overlay) overlay.classList.remove('active');
    if (modal) modal.classList.remove('open');
  }

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (heroStartBtn) heroStartBtn.addEventListener('click', () => openModal('link'));
  if (heroContact) heroContact.addEventListener('click', () => openModal('link'));
  if (btnConnect) btnConnect.addEventListener('click', () => openModal('link'));
  if (footerConnect) footerConnect.addEventListener('click', () => openModal('link'));
  if (btnLaunchNewCheck) btnLaunchNewCheck.addEventListener('click', () => openModal('link'));

  modulePills.forEach((pill) => {
    pill.addEventListener('click', () => {
      const mod = pill.getAttribute('data-module');
      setModalModule(mod);
    });
  });

  // File drag & drop
  if (fileDropzone && fileUploadInput) {
    fileDropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      fileDropzone.classList.add('dragover');
    });

    fileDropzone.addEventListener('dragleave', () => {
      fileDropzone.classList.remove('dragover');
    });

    fileDropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      fileDropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFileSelect(e.dataTransfer.files[0]);
      }
    });

    fileUploadInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
      }
    });
  }

  function handleFileSelect(file) {
    if (file.size > (['document','offer'].includes(activeModule) ? 20 : ['screenshot','qr'].includes(activeModule) ? 10 : 50) * 1024 * 1024) {
      showToast(['document','offer'].includes(activeModule) ? 'Choose a document smaller than 20 MiB' : ['screenshot','qr'].includes(activeModule) ? 'Choose an image smaller than 10 MiB' : 'Choose a file smaller than 50 MB');
      return;
    }
    const supported = ['screenshot','qr'].includes(activeModule) ? /\.(png|jpe?g|webp)$/i : activeModule === 'document' ? /\.(pdf|docx)$/i : activeModule === 'offer' ? /\.(pdf|docx)$/i : /\.(mp4|webm|mov|mp3|wav|m4a|aac|png|jpe?g|webp)$/i;
    if (!supported.test(file.name)) {
      showToast('Choose a supported file type for this module');
      return;
    }
    activeSelectedFile = file;
    if (['screenshot','qr'].includes(activeModule)) showScreenshotPreview(file);
    if (activeModule==='media') showMediaIntake(file);
    if (selectedFileName) selectedFileName.textContent = `${file.name} · ${(file.size / (1024 * 1024)).toFixed(2)} MB`;
    if (fileSelectedInfo) fileSelectedInfo.style.display = 'flex';
    if (dropzonePrompt) dropzonePrompt.style.display = 'none';
  }

  if (btnRemoveFile) {
    btnRemoveFile.addEventListener('click', (e) => {
      e.stopPropagation();
      if (['screenshot','qr','document','media','offer'].includes(activeModule)) {
        clearScreenshotInput();
        return;
      }
      activeSelectedFile = null;
      if (fileUploadInput) fileUploadInput.value = '';
      if (fileSelectedInfo) fileSelectedInfo.style.display = 'none';
      if (dropzonePrompt) dropzonePrompt.style.display = 'flex';
    });
  }

  // Cancel button
  if (btnCancelScan) {
    btnCancelScan.addEventListener('click', () => {
      if (activeAbortController) {
        activeAbortController.abort();
        activeAbortController = null;
      }
      const overlay = document.getElementById('processingOverlay');
      if (overlay) overlay.classList.remove('active');
      showToast('Assessment cancelled by user');
    });
  }

  // Form submission to real backend
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      const urlVal = document.getElementById('inputUrlField')?.value.trim() || '';
      const textVal = document.getElementById('inputTextField')?.value || '';

      // Validation
      if (activeModule === 'link' && !urlVal) {
        showToast('Please enter a target URL or domain');
        return;
      }
      if (activeModule === 'message' && !textVal) {
        showToast('Please enter message text to inspect');
        return;
      }
      if (activeModule === 'offer' && !textVal && !activeSelectedFile) {
        showToast('Please enter an offer or attach a PDF');
        return;
      }
      if (['screenshot', 'qr', 'document', 'media'].includes(activeModule) && !activeSelectedFile) {
        showToast('Please select or upload a file for analysis');
        return;
      }


      const overlay = document.getElementById('processingOverlay');
      const stageText = document.getElementById('processingStageText');
      const stageSub = document.getElementById('processingStageSub');

      if (overlay) overlay.classList.add('active');
      if (stageText) stageText.textContent = 'Submitting content for analysis...';
      if (stageSub) stageSub.textContent = ['link', 'message'].includes(activeModule) ? 'Waiting for live backend stage updates.' : 'Waiting for the backend response.';

      activeAbortController = new AbortController();
      const requestController = activeAbortController;
      const submittedModule = activeModule;
      const uploadedScreenshot = ['screenshot','qr','document','media','offer'].includes(activeModule) ? activeSelectedFile : null;

      try {
        let response;
        if (['link','message'].includes(submittedModule) || submittedModule==='offer' && !uploadedScreenshot) {
          const body = submittedModule==='link'?{url:urlVal}:submittedModule==='message'?{message:textVal}:{offer:textVal};
          response=await fetch(`/api/check/${submittedModule}?stream=true`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:requestController.signal});
        } else {
          const formData=new FormData(); formData.append('file',uploadedScreenshot);
          if(submittedModule!=='qr') formData.append('language',document.getElementById('screenshotLanguage').value);
          if(submittedModule==='offer') formData.append('offer',textVal);
          response=await fetch(`/api/check/${submittedModule}?stream=true`,{method:'POST',body:formData,signal:requestController.signal});
        }

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          const detail = Array.isArray(errData.detail) ? errData.detail.map(item => item.msg).join('; ') : errData.detail;
          throw new Error(detail || `Backend unavailable (HTTP ${response.status})`);
        }

        const assessmentData = ['link', 'message', 'screenshot', 'qr', 'document', 'media', 'offer'].includes(activeModule)
          ? await readLinkCheckStream(response, stage => {
              if (stageText) stageText.textContent = stage;
              if (stageSub) stageSub.textContent = 'Live backend processing stage';
            })
          : await response.json();
        if (requestController.signal.aborted) return;
        if(submittedModule==='offer' && !uploadedScreenshot && assessmentData.submitted_text!==textVal) throw new Error('Offer input/result mismatch; retry your submission.');
        if (uploadedScreenshot) {
          const digest = await crypto.subtle.digest('SHA-256', await uploadedScreenshot.arrayBuffer());
          const hash = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
          if (requestController.signal.aborted) return;
          if ((assessmentData.image || assessmentData.file)?.sha256 !== hash) throw new Error('Upload/result mismatch: image evidence was not displayed. Retry your upload.');
          if (submittedModule==='media') {
            if(mediaResultUrl)URL.revokeObjectURL(mediaResultUrl); mediaFile=uploadedScreenshot;mediaResultId=assessmentData.id;mediaResultUrl=URL.createObjectURL(uploadedScreenshot);
          } else if(submittedModule==='offer') { offerFile=uploadedScreenshot;offerResultId=assessmentData.id;offerText=textVal;
          } else if (submittedModule === 'document') {
            documentFile = uploadedScreenshot; documentResultId = assessmentData.id; documentLanguage = document.getElementById('screenshotLanguage').value;
          } else if (submittedModule === 'qr') {
            if (qrResultUrl) URL.revokeObjectURL(qrResultUrl);
            qrFile = uploadedScreenshot; qrResultId = assessmentData.id; qrResultUrl = URL.createObjectURL(uploadedScreenshot);
          } else {
          if (screenshotResultUrl) URL.revokeObjectURL(screenshotResultUrl);
          currentScreenshotFile = uploadedScreenshot;
          screenshotResultId = assessmentData.id;
          screenshotResultUrl = URL.createObjectURL(uploadedScreenshot);
          }
        }

        if(submittedModule==='offer') { offerText=textVal;offerFile=uploadedScreenshot;offerResultId=assessmentData.id; }
        // Success
        closeModal();
        renderAssessment(assessmentData);
        window.history.replaceState(null, '', `#/results/${assessmentData.id}`);

        // Scroll to evidence section
        const archSec = document.getElementById('architecture');
        if (archSec) archSec.scrollIntoView({ behavior: 'smooth' });

        // Update dashboard telemetry and history
        loadDashboardData();
        showToast('Assessment completed successfully');
      } catch (err) {
        if (err.name === 'AbortError') return;
        console.error('Assessment failed:', err);
        if (overlay) overlay.classList.remove('active');
        showToast(err.message === 'Failed to fetch' ? 'Cannot reach the backend. Start the API to run a real check.' : `Analysis failed: ${err.message}`);
      } finally {
        if (activeAbortController === requestController) activeAbortController = null;
      }
    });
  }

  // Close modal when clicking outside
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal && modal.classList.contains('open')) {
      closeModal();
    }
  });
}

/* --------------------------------------------------------------------------
   8. REAL-BACKEND ASSESSMENT RENDERING & EVIDENCE
   -------------------------------------------------------------------------- */
function renderScreenshotOverview(data, overview) {
  overview.replaceChildren();
  const heading = document.createElement('div');
  heading.className = 'module-risk-heading';
  const verdict = document.createElement('strong');
  verdict.textContent = data.risk_category;
  const label = document.createElement('span');
  label.textContent = `Screenshot Check · OCR ${data.ocr?.status || 'details not retained'}`;
  heading.append(verdict, label);
  const explanation = document.createElement('p');
  explanation.textContent = data.explanation;
  overview.append(heading, explanation);
  const actions = document.createElement('div');
  actions.className = 'screenshot-actions';
  const back = document.createElement('button');
  back.className = 'btn-secondary-action';
  back.textContent = 'Back to input';
  const openInput = () => {
    setModalModule('screenshot');
    if (currentScreenshotFile && screenshotResultId === data.id) {
      activeSelectedFile = currentScreenshotFile;
      showScreenshotPreview(currentScreenshotFile);
      document.getElementById('selectedFileName').textContent = currentScreenshotFile.name;
      document.getElementById('fileSelectedInfo').style.display = 'flex';
      document.getElementById('dropzonePrompt').style.display = 'none';
      document.getElementById('screenshotLanguage').value = data.ocr?.selected_language || 'en';
    }
    document.getElementById('contactModal').classList.add('open');
  };
  back.onclick = openInput;
  actions.append(back);
  if (!data.image) {
    const notice = document.createElement('p');
    notice.textContent = 'Only assessment metadata was saved. Upload the screenshot again to view OCR evidence.';
    overview.append(actions, notice);
    return;
  }
  const retry = document.createElement('button');
  retry.className = 'btn-secondary-action';
  retry.textContent = 'Retry screenshot';
  retry.onclick = () => {
    openInput();
    if (activeSelectedFile) document.getElementById('assessmentForm').requestSubmit();
  };
  const reset = document.createElement('button');
  reset.className = 'btn-secondary-action';
  reset.textContent = 'Reset screenshot';
  reset.onclick = () => clearScreenshotInput(true);
  actions.append(retry, reset);
  overview.append(actions);
  const note = document.createElement('p');
  note.className = 'screenshot-note';
  note.textContent = `${data.image.original_filename} · ${data.image.validated_format} · ${data.image.width} × ${data.image.height}. ${data.ocr.region_count} real OCR regions. ${data.processing_coverage.uncertain_regions} uncertain. AI: ${data.message_analysis?.ai?.status || 'unavailable'}. Image authenticity and sender identity are unverified.`;
  overview.append(note);
  if (screenshotResultUrl && screenshotResultId === data.id) {
    const stage = document.createElement('div');
    stage.className = 'screenshot-evidence-stage';
    const image = document.createElement('img');
    image.src = screenshotResultUrl;
    image.alt = 'Actual uploaded screenshot with real OCR evidence';
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${data.image.width} ${data.image.height}`);
    svg.setAttribute('aria-label', 'Actual OCR region coordinates');
    svg.setAttribute('role', 'img');
    const paint = (ids = null) => {
      svg.replaceChildren();
      for (const region of data.ocr_regions) {
        if (ids && !ids.includes(region.region_id)) continue;
        const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
        polygon.setAttribute('points', region.bounding_box.points.map(point => point.join(',')).join(' '));
        polygon.setAttribute('fill', 'rgba(255,170,0,.10)');
        polygon.setAttribute('stroke', ids ? '#d13b37' : '#0d9488');
        polygon.setAttribute('stroke-width', '2');
        polygon.setAttribute('vector-effect', 'non-scaling-stroke');
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = `${region.region_id}: ${region.text} · OCR confidence ${region.confidence ?? 'unavailable'}`;
        polygon.append(title);
        svg.append(polygon);
      }
    };
    paint();
    stage.append(image, svg);
    overview.append(stage);
    const controls = document.createElement('div');
    controls.className = 'screenshot-actions';
    for (const [label, ids] of [['Show all OCR boxes', null], ...(data.grounded_findings || []).map(item => [`Highlight: ${item.text}`, item.region_ids])]) {
      const button = document.createElement('button');
      button.className = 'btn-secondary-action';
      button.textContent = label;
      button.onclick = () => paint(ids);
      controls.append(button);
    }
    overview.append(controls);
  }
  for (const [title, value] of [
    ['Review details · Actual OCR text', data.extracted_text],
    ['OCR regions · Confidence and bounding boxes', data.ocr_regions],
    ['Grounded findings · Evidence mapped to regions', data.grounded_findings],
    ['Embedded URLs · Actual Link Check results', data.url_assessments],
    ['Uncertain URL candidates · Not contacted', data.uncertain_url_candidates],
    ['Message and Qwen analysis', data.message_analysis],
    ['Payment observations · Unverified identities', data.payment_observations],
    ['QR evidence · Separate decoder', data.qr],
    ['OCR models and processing coverage', { ocr: data.ocr, coverage: data.processing_coverage }],
    ['Exact backend result · Available until refresh', data]
  ]) {
    const detail = document.createElement('details');
    detail.className = 'module-protect';
    detail.open = title === 'Review details · Actual OCR text';
    const summary = document.createElement('summary');
    summary.textContent = title;
    const pre = document.createElement('pre');
    pre.className = 'link-observation-json';
    if (value === data) pre.id = 'screenshotResultJson';
    pre.textContent = typeof value === 'string' ? value || 'No readable text recognized.' : JSON.stringify(value, null, 2);
    detail.append(summary, pre);
    overview.append(detail);
  }
}

function renderMessageOverview(data, overview) {
  overview.replaceChildren();
  const heading = document.createElement('div');
  heading.className = 'module-risk-heading';
  const verdict = document.createElement('strong');
  verdict.textContent = data.risk_category;
  const label = document.createElement('span');
  label.textContent = 'Message Check · Detailed check evidence';
  heading.append(verdict, label);
  const explanation = document.createElement('p');
  explanation.textContent = data.explanation;
  overview.append(heading, explanation);
  const back = document.createElement('button');
  back.className = 'btn-secondary-action';
  back.textContent = 'Back to input';
  back.onclick = () => {
    setModalModule('message');
    document.getElementById('inputTextField').value = data.submitted_text || '';
    updateMessageCount();
    document.getElementById('contactModal').classList.add('open');
    document.getElementById('inputTextField').focus();
  };
  overview.append(back);
  if (typeof data.submitted_text !== 'string') {
    const notice = document.createElement('p');
    notice.textContent = 'Only assessment metadata was saved. Paste the message again to see evidence and detailed checks.';
    overview.append(notice);
    return;
  }
  const note = document.createElement('p');
  note.textContent = `AI: ${data.ai?.status || 'unavailable'} · ${data.ai?.model_used || 'No model ran'}. ${data.ai?.error || ''} Original text and detailed results are not saved in history.`;
  overview.append(note);
  const detail = document.createElement('details');
  detail.className = 'module-protect';
  detail.open = true;
  const summary = document.createElement('summary');
  summary.textContent = 'Review details · Highlighted evidence';
  const message = document.createElement('div');
  message.className = 'message-evidence-text';
  const chars = Array.from(data.submitted_text);
  const spans = [...(data.deterministic_findings || []), ...(data.ai_interpretations || [])];
  const boundaries = [...new Set([0, chars.length, ...spans.flatMap(item => [item.start, item.end])])].filter(n => n >= 0 && n <= chars.length).sort((a, b) => a - b);
  for (let i = 0; i < boundaries.length - 1; i++) {
    const start = boundaries[i], end = boundaries[i + 1];
    const matching = spans.filter(item => item.start <= start && end <= item.end);
    const node = document.createElement(matching.length ? 'mark' : 'span');
    node.textContent = chars.slice(start, end).join('');
    if (matching.length) node.title = matching.map(item => `${item.category} · ${item.context}`).join('\n');
    message.append(node);
  }
  detail.append(summary, message);
  overview.append(detail);
  for (const [label, value] of [
    ['Extracted entities · Exact text offsets', data.extracted_entities],
    ['Deterministic rules · Context and evidence', data.deterministic_findings],
    ['External URL observations · Real Link Check', data.url_assessments],
    ['AI interpretation · Grounded Qwen output', data.ai],
    ['Language coverage and limitations', data.language]
  ]) {
    const section = document.createElement('details');
    section.className = 'module-protect';
    const title = document.createElement('summary');
    title.textContent = label;
    const pre = document.createElement('pre');
    pre.className = 'link-observation-json';
    pre.textContent = JSON.stringify(value, null, 2);
    section.append(title, pre);
    overview.append(section);
  }
  const raw = document.createElement('details');
  raw.className = 'module-protect';
  const rawTitle = document.createElement('summary');
  rawTitle.textContent = 'Exact backend result · Available until refresh';
  const pre = document.createElement('pre');
  pre.id = 'messageResultJson';
  pre.className = 'link-observation-json';
  pre.textContent = JSON.stringify(data, null, 2);
  raw.append(rawTitle, pre);
  overview.append(raw);
}

function renderQrOverview(data, overview) {
  overview.replaceChildren();
  const heading = document.createElement('div'); heading.className = 'module-risk-heading';
  const title = document.createElement('strong'); title.textContent = data.risk_category;
  const sub = document.createElement('span'); sub.textContent = `QR Check · ${data.qr_count ?? 0} decoded code(s) · Detailed check evidence`;
  heading.append(title, sub); overview.append(heading);
  const explanation = document.createElement('p'); explanation.textContent = data.explanation; overview.append(explanation);
  const actions = document.createElement('div'); actions.className = 'screenshot-actions';
  const reopen = () => { setModalModule('qr'); clearScreenshotInput(); if (qrFile && qrResultId === data.id) { activeSelectedFile = qrFile; showScreenshotPreview(qrFile); document.getElementById('selectedFileName').textContent = qrFile.name; document.getElementById('fileSelectedInfo').style.display = 'flex'; document.getElementById('dropzonePrompt').style.display = 'none'; } document.getElementById('contactModal').classList.add('open'); };
  for (const [label, action] of [['Back to input',reopen], ['Retry QR image',() => { reopen(); if (activeSelectedFile) document.getElementById('assessmentForm').requestSubmit(); }], ['Reset QR image',() => { clearScreenshotInput(true); }]]) {
    const button=document.createElement('button'); button.type='button'; button.className='btn-secondary-action'; button.textContent=label; button.onclick=action; actions.append(button);
  }
  overview.append(actions);
  if (qrResultUrl && qrResultId === data.id) { const image=document.createElement('img'); image.src=qrResultUrl; image.alt='Actual uploaded QR image'; image.className='screenshot-input-preview'; overview.append(image); }
  const addDetails=(label,value,id) => { const details=document.createElement('details'); details.className='module-protect'; const summary=document.createElement('summary'); summary.textContent=label; const pre=document.createElement('pre'); pre.className='link-observation-json'; pre.textContent=typeof value==='string' ? value : JSON.stringify(value,null,2); if(id) pre.id=id; details.append(summary,pre); overview.append(details); };
  if (!data.codes) { const notice=document.createElement('p'); notice.textContent='Only metadata was retained. Upload the image again to decode its QR payloads.'; overview.append(notice); return; }
  for (const code of data.codes) {
    const label=document.createElement('h4'); label.textContent=`QR ${code.id} · ${code.type} · ${code.risk_category}`; overview.append(label);
    const raw=document.createElement('pre'); raw.className='link-observation-json'; raw.textContent=code.payload; raw.dataset.qrPayloadId=code.id; overview.append(raw);
    const copy=document.createElement('button'); copy.type='button'; copy.className='btn-secondary-action'; copy.textContent=data.codes.length===1 ? 'Copy Destination' : `Copy Destination · QR ${code.id}`;
    copy.onclick=async () => { try { await navigator.clipboard.writeText(code.payload); showToast('Copied original decoded payload'); } catch { showToast('Clipboard unavailable. Select the displayed raw payload to copy.'); } }; overview.append(copy);
    addDetails(`QR ${code.id} · Review parsed fields · Self-declared`,code.parsed_fields);
    addDetails(`QR ${code.id} · Link Check results`,code.link_results);
    if (code.message_result) addDetails(`QR ${code.id} · Message Check result`,code.message_result);
    if (code.parse_warnings.length) addDetails(`QR ${code.id} · Parsing limitations`,code.parse_warnings);
  }
  addDetails('QR decoder · Actual observations',data.decoder);
  addDetails('Exact backend result · Temporary until refresh',data,'qrResultJson');
}

function mediaPreview(file,url,id) {
  const node=document.createElement(file.type.startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(file.name)?'img':file.type.startsWith('audio/') || /\.(wav|mp3|m4a|aac)$/i.test(file.name)?'audio':'video');
  node.id=id;node.src=url;node.className='screenshot-input-preview';if(node.tagName!=='IMG'){node.controls=true;node.preload='metadata';}else node.alt='Actual uploaded media';
  return node;
}
function showMediaIntake(file) {
  document.getElementById('mediaIntakePreview')?.remove();
  if(screenshotIntakeUrl)URL.revokeObjectURL(screenshotIntakeUrl);screenshotIntakeUrl=URL.createObjectURL(file);
  document.getElementById('screenshotIntake').append(mediaPreview(file,screenshotIntakeUrl,'mediaIntakePreview'));
}
function renderMediaOfferOverview(data,overview) {
  overview.replaceChildren();
  const isMedia=data.module_type==='media';
  const heading=document.createElement('div');heading.className='module-risk-heading';const title=document.createElement('strong');title.textContent=data.risk_category;
  const sub=document.createElement('span');sub.textContent=isMedia?`Content: ${data.content_risk || 'details not retained'} · Authenticity: ${data.authenticity?.assessment || 'Unable to Assess'}`:`Offer: ${data.offer_type || 'unknown'} · ${data.input_source || 'details not retained'}`;heading.append(title,sub);overview.append(heading);
  const note=document.createElement('p');note.textContent=data.explanation;overview.append(note);
  const reopen=()=>{setModalModule(data.module_type);clearScreenshotInput();const file=isMedia?mediaFile:offerFile;const resultId=isMedia?mediaResultId:offerResultId;if(resultId===data.id){document.getElementById('inputTextField').value=isMedia?'':offerText;updateMessageCount();if(file){activeSelectedFile=file;document.getElementById('selectedFileName').textContent=file.name;document.getElementById('fileSelectedInfo').style.display='flex';document.getElementById('dropzonePrompt').style.display='none';if(isMedia)showMediaIntake(file);}}document.getElementById('contactModal').classList.add('open');};
  const actions=document.createElement('div');actions.className='screenshot-actions';for(const [label,action] of [['Back to input',reopen],[isMedia?'Retry media':'Retry offer',()=>{reopen();document.getElementById('assessmentForm').requestSubmit();}],[isMedia?'Reset media':'Reset offer',()=>clearScreenshotInput(true)]]){const b=document.createElement('button');b.type='button';b.className='btn-secondary-action';b.textContent=label;b.onclick=action;actions.append(b);}overview.append(actions);
  const detail=(label,value,id)=>{const d=document.createElement('details');d.className='module-protect';const summary=document.createElement('summary');summary.textContent=label;const pre=document.createElement('pre');pre.className='link-observation-json';pre.textContent=typeof value==='string'?value:JSON.stringify(value,(k,v)=>k==='preview_png'?'Preview bytes omitted':v,2);if(id)pre.id=id;d.append(summary,pre);overview.append(d);};
  if(!data.file && data.submitted_text==null && !data.document_analysis) { const note=document.createElement('p');note.textContent='Only metadata was retained. Submit the original input again to view details.';overview.append(note);return; }
  if(isMedia){
    if(mediaFile&&mediaResultUrl&&mediaResultId===data.id)overview.append(mediaPreview(mediaFile,mediaResultUrl,'actualMediaPreview'));
    detail('Review details · Actual file, metadata and coverage',{file:data.file,media:data.media,audio:data.audio_extraction,coverage:data.coverage});
    detail('Authenticity · Detector availability and scope',data.authenticity);
    for(const frame of data.frames || [])detail(`${frame.frame_id} · ${frame.status==='failed'?'Failed sample':frame.timestamp_seconds==null?'Image':frame.timestamp_seconds.toFixed(2)+'s'} · Actual OCR`,frame);
    detail('Speech · Actual Whisper transcript and timestamps',data.transcript);
    const times=[...(data.frames || []).map(f=>({start:f.timestamp_seconds,label:f.frame_id})),...(data.transcript?.segments || []).map(x=>({start:x.start,label:`Speech ${x.start.toFixed(2)}–${x.end.toFixed(2)}s`}))];
    for(const x of times)if(x.start!=null){const b=document.createElement('button');b.type='button';b.className='btn-secondary-action';b.textContent=`Review at ${x.start.toFixed(2)}s · ${x.label}`;b.onclick=()=>{const player=document.getElementById('actualMediaPreview');if(player&&player.tagName!=='IMG'){player.currentTime=x.start;player.scrollIntoView({behavior:'smooth'});}};overview.append(b);}
  }else{
    detail('Original offer · Actual submitted text',data.submitted_text || 'Document input; inspect actual pages below.');
    detail('Review details · Extracted offer entities',{classification:data.classification,entities:data.extracted_entities,coverage:data.coverage});
    detail('Qwen · Actual grounded contextual results',data.ai || data.page_analyses?.map(p=>({reference:p.reference,ai:p.analysis.ai})));
    if(data.document_analysis)detail('Offer document · Actual page extraction and evidence',data.document_analysis);
  }
  detail('Links · Real shared Link Check',data.url_assessments);
  detail('Backend result · Actual assessment',data,isMedia?'mediaResultJson':'offerResultJson');
}

function renderDocumentOverview(data, overview) {
  overview.replaceChildren();
  const heading=document.createElement('div'); heading.className='module-risk-heading';
  const title=document.createElement('strong'); title.textContent=data.risk_category;
  const sub=document.createElement('span'); sub.textContent=`Document Check · ${data.document?.parse_status || 'details not retained'} · Detailed check evidence`; heading.append(title,sub); overview.append(heading);
  const explanation=document.createElement('p'); explanation.textContent=data.explanation; overview.append(explanation);
  const actions=document.createElement('div'); actions.className='screenshot-actions';
  const reopen=() => { setModalModule('document'); clearScreenshotInput(); if(documentFile && documentResultId===data.id) { activeSelectedFile=documentFile; document.getElementById('selectedFileName').textContent=documentFile.name; document.getElementById('fileSelectedInfo').style.display='flex'; document.getElementById('dropzonePrompt').style.display='none'; document.getElementById('screenshotLanguage').value=data.pages?.find(p=>p.ocr)?.ocr?.selected_language || documentLanguage; } document.getElementById('contactModal').classList.add('open'); };
  for(const [label,action] of [['Back to input',reopen],['Retry document',()=>{reopen();if(activeSelectedFile)document.getElementById('assessmentForm').requestSubmit();}],['Reset document',()=>clearScreenshotInput(true)]]) { const b=document.createElement('button');b.type='button';b.className='btn-secondary-action';b.textContent=label;b.onclick=action;actions.append(b); } overview.append(actions);
  if(!data.file) { const note=document.createElement('p');note.textContent='Only metadata was retained. Upload the document again to view page evidence.';overview.append(note);return; }
  const meta=document.createElement('p');meta.className='screenshot-note';meta.textContent=`${data.file.original_filename} · ${data.file.validated_type} · ${(data.file.file_size_bytes/1024).toFixed(1)} KiB · ${data.coverage.total_pages ?? 'No fixed'} pages · ${data.coverage.pages_parsed ?? data.coverage.logical_blocks_parsed} processed · ${data.coverage.pages_ocr_processed} OCR · Malware: ${data.malware.status}. ${data.coverage.analysis_complete ? 'Required checks completed.' : 'Coverage/checks are incomplete.'}`;overview.append(meta);
  const details=(label,value,id)=>{const d=document.createElement('details');d.className='module-protect';const summary=document.createElement('summary');summary.textContent=label;const pre=document.createElement('pre');pre.className='link-observation-json';pre.textContent=typeof value==='string'?value:JSON.stringify(value,(key,v)=>key==='preview_png'?'Rendered preview bytes omitted from JSON view':v,2);if(id)pre.id=id;d.append(summary,pre);overview.append(d);};
  const preview=data.pages?.find(p=>p.preview_png);
  if(preview) {const img=document.createElement('img');img.src=preview.preview_png;img.alt=`Actual document rendered preview · ${preview.reference}`;img.className='screenshot-input-preview';overview.append(img);}
  details('Review details · File metadata and actual PDF/DOCX structure',{file:data.file,document:data.document});
  details('Malware scan · Actual ClamAV result',data.malware);
  details('Processing coverage · Unreadable and skipped pages',data.coverage);
  for(const page of data.pages) {
    details(`${page.reference} · Actual ${page.source} text · ${page.status}`,page.text || 'No meaningful readable text found');
    if(page.ocr)details(`${page.reference} · Actual OCR regions and confidence`,page.ocr);
    if(page.message_analysis)details(`${page.reference} · Grounded Message Check`,page.message_analysis);
  }
  details('Embedded and visible links · Real Link Check results',data.url_assessments);
  details('Page-linked evidence · Grounded findings',data.grounded_findings);
  details('Backend result · Preview bytes omitted',data,'documentResultJson');
}

function renderPlainResult(data, overview) {
  const result = summarizeResult(data);
  const technical = document.createElement('details');
  technical.className = 'result-technical';
  const technicalTitle = document.createElement('summary');
  technicalTitle.textContent = 'See full evidence and technical details';
  const body = document.createElement('div');
  body.className = 'result-technical-body';
  const visible = [];
  for (const child of [...overview.children]) {
    // Retain original input/retry controls and actual visual previews beside the simple result.
    if (child.matches('.screenshot-actions, .screenshot-evidence-stage, .screenshot-input-preview, video, audio') || child.tagName === 'BUTTON' && child.textContent === 'Back to input') visible.push(child);
    else body.append(child);
  }
  body.querySelectorAll('details').forEach(d => d.open = false);
  technical.append(technicalTitle, body);
  overview.replaceChildren();
  const icon = name => {
    const paths = {shield:'<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6z"/><path d="m8 12 3 3 5-6"/>',lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',money:'<rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="12" cy="12" r="3"/><path d="M6 12h1m10 0h1"/>'};
    return `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.shield}</svg>`;
  };
  const hero = document.createElement('section');
  hero.className = `simple-result simple-result--${result.tone}`;
  hero.setAttribute('aria-label', 'Your result in simple terms');
  const percent = result.score ?? 0;
  hero.innerHTML = `<div class="simple-result-top"><div class="result-ring ${result.score===null?'result-ring--empty':''}" style="--points:${percent}" role="img" aria-label="${result.score===null?'Score unavailable':percent+' out of 100 warning points'}"><div><strong>${result.score ?? '—'}</strong><span>/ 100</span></div></div><div class="simple-result-copy"><span class="result-eyebrow">${data.demo?'Illustrative example':'YOUR RESULT'} · WARNING SCORE</span><h3>${escapeHtml(result.title)}</h3><p>${escapeHtml(result.description)}</p><span class="result-completeness">${result.incomplete?'◐ Some checks are missing':'✓ Available checks completed'}</span></div></div><div class="result-meter" aria-hidden="true"><span></span><span></span><span></span><i style="left:${percent}%"></i></div><div class="result-meter-labels"><span>Fewer warning signs</span><span>More warning signs</span></div><p class="result-score-note">${result.score===null?'Submit the original content again for a live score.':'Higher points mean stronger observed warnings. This is not a percentage chance of fraud.'} ${result.incomplete?'Missing checks are unknown; a low score does not mean safe.':''}</p>`;
  overview.append(hero);
  const stats = document.createElement('div'); stats.className='result-stats';
  for (const [value,label,tone] of [[result.score===null?'—':result.findings.length,'Warning signs','warning'],[result.score===null?'—':result.completed,'Checks completed','done'],[result.score===null?'—':result.missing,'Checks need attention','missing']]) {
    const item=document.createElement('div');item.className=`result-stat result-stat--${tone}`;
    item.innerHTML=`${icon(tone==='warning'?'shield':tone==='missing'?'clock':'shield')}<strong>${value}</strong><span>${label}</span>`;stats.append(item);
  }
  overview.append(stats);
  const signals=document.createElement('div');signals.className='result-signals';
  const seen=new Set();
  for (const finding of result.findings) {
    const signal=plainSignal(finding);if(seen.has(signal.title))continue;seen.add(signal.title);
    const card=document.createElement('div');card.className='result-signal';
    card.innerHTML=`<div class="result-signal-icon">${icon(signal.icon)}</div><div><h4>${escapeHtml(signal.title)}</h4><p>${escapeHtml(signal.detail)}</p><blockquote>${escapeHtml(String(finding.observation || '').slice(0,240))}</blockquote></div>`;
    signals.append(card);if(seen.size===3)break;
  }
  if(!signals.children.length){const p=document.createElement('p');p.className='result-no-signals';p.textContent=result.score===null?'Detailed evidence is not available in this saved view.':'No warning signs found by the checks that ran. This does not confirm the content is genuine.';signals.append(p);}
  overview.append(signals);
  const next=document.createElement('div');next.className='result-next-step';
  next.innerHTML=`${icon('shield')}<div><span>YOUR NEXT STEP</span><strong>${escapeHtml(result.nextStep)}</strong></div>`;overview.append(next);
  if(data.module_type==='media'){const p=document.createElement('p');p.className='result-score-note';p.textContent='This score reviews suspicious content. Deepfake and voice-clone detection are unavailable; it does not measure whether media is real.';overview.append(p);}
  if(result.missing){const limits=document.createElement('details');limits.className='result-missing-details';const title=document.createElement('summary');title.textContent='What could we not check?';limits.append(title);const ul=document.createElement('ul');
    const names=new Set();for(const c of [...(data.unavailable_checks || []),...(data.checks_performed || []).filter(c=>!['passed','flagged','completed'].includes(c.status))]){if(names.has(c.name))continue;names.add(c.name);const li=document.createElement('li');const n=String(c.name||'');li.textContent=/reputation|web risk/i.test(n)?'Known dangerous-link lists could not be checked.':/AI|Qwen|contextual/i.test(n)?'The AI review could not complete.':/RDAP|registration/i.test(n)?'We could not confirm the website registration details.':/HEAD|redirect/i.test(n)?'We could not fully follow the link destination.':/authentic|identity|organisation|regulat/i.test(n)?'The sender, organisation or authenticity has not been independently verified.':/coverage|page/i.test(n)?'Some content could not be fully read or checked.':n;ul.append(li);}limits.append(ul);overview.append(limits);}
  overview.append(...visible,technical);
  const method=document.createElement('details');method.className='result-missing-details';method.innerHTML='<summary>How is the score calculated?</summary><p>A unique strong warning adds 85 points; a caution adds 30. Further distinct warnings add 15% of their points, capped at 99. A known dangerous-link match sets at least 95; a malware signature match sets 100. Repeated copies of the same evidence count once. Missing tools add no points and are shown separately. This is a display guide, not a validated fraud probability.</p>';overview.append(method);
}

function renderAssessment(data) {
  currentAssessment = data;
  const evidenceTab = document.querySelector('[data-tab="tab-findings"]');
  if (evidenceTab?.firstChild) evidenceTab.firstChild.textContent = data.module_type === 'screenshot' ? 'Evidence & Findings (' : 'Warning signs (';
  const emptyState = document.getElementById('evidenceEmptyState');
  const activeState = document.getElementById('evidenceActiveState');
  if (!emptyState || !activeState) return;

  emptyState.style.display = 'none';
  activeState.style.display = 'block';

  // Badges & Headers
  const badgeModule = document.getElementById('evidenceModuleBadge');
  const title = document.getElementById('evidenceTitle');
  const riskBadge = document.getElementById('evidenceRiskBadge');
  const timestamp = document.getElementById('evidenceTimestamp');
  const inputSummary = document.getElementById('evidenceInputSummary');

  if (badgeModule) badgeModule.textContent = (data.module_type || 'CHECK').toUpperCase();
  if (title) title.textContent = `${(data.module_type || 'Threat')[0].toUpperCase()}${(data.module_type || 'Threat').slice(1)} check result`;
  if (inputSummary) inputSummary.textContent = data.input_summary || 'Submitted content';
  activeState.querySelector('.url-excerpt-box > span').textContent = data.demo ? 'Illustrative sample content' : 'Analyzed submission';
  let overview = document.getElementById('assessmentOverview');
  if (!overview) {
    overview = document.createElement('div');
    overview.id = 'assessmentOverview';
    overview.className = 'assessment-overview';
    activeState.querySelector('.evidence-tabs').before(overview);
  }
  overview.hidden = !data.demo && !['link', 'message', 'screenshot', 'qr', 'document', 'media', 'offer'].includes(data.module_type);
  if (data.demo) {
    overview.innerHTML = `<div class="module-risk-heading"><strong>Clarity for your next step.</strong><span>${data.demo_score === null ? 'Unable to assess' : `${data.demo_score} / 100 · Demo score`}</span></div>
      <div class="module-risk-scale"><span>Low</span><span>Medium</span><span>High</span></div>
      <p>Illustrative assessment · Demo. ${data.demo_score === null ? 'Authenticity cannot be determined from this example.' : 'Do not pay or share private information before verifying.'} No live checks were performed.</p>
      <details class="module-protect"><summary>Protect yourself · View details</summary><ul>${data.recommended_actions.map(action => `<li>${escapeHtml(action)}</li>`).join('')}</ul></details>`;
  }
  if (data.module_type === 'link' && !data.demo) {
    overview.innerHTML = `<div class="module-risk-heading"><strong>${escapeHtml(data.risk_category)}</strong><span>Live Link Check · Detailed check evidence</span></div><p>${escapeHtml(data.explanation)}</p>`;
    const observations = data.provider_info?.link_analysis || data;
    for (const [name, label] of [['dns', 'DNS observations'], ['rdap', 'Domain registration · RDAP'], ['reputation', 'Reputation provider result'], ['redirects', 'Redirect chain · HEAD inspection']]) {
      const detail = document.createElement('details');
      detail.className = 'module-protect';
      const summary = document.createElement('summary');
      summary.textContent = `${label} · ${observations[name]?.status || 'unavailable'}`;
      const pre = document.createElement('pre');
      pre.className = 'link-observation-json';
      pre.textContent = JSON.stringify(observations[name] || { status: 'unavailable' }, null, 2);
      detail.append(summary, pre);
      overview.appendChild(detail);
    }
    const raw = document.createElement('details');
    raw.className = 'module-protect';
    raw.innerHTML = '<summary>Exact backend result</summary>';
    const pre = document.createElement('pre');
    pre.id = 'linkResultJson';
    pre.className = 'link-observation-json';
    pre.textContent = JSON.stringify(data, null, 2);
    raw.appendChild(pre);
    overview.appendChild(raw);
  }
  if (data.module_type === 'message' && !data.demo) renderMessageOverview(data, overview);
  if (data.module_type === 'screenshot' && !data.demo) renderScreenshotOverview(data, overview);
  if (data.module_type === 'qr' && !data.demo) renderQrOverview(data, overview);
  if (data.module_type === 'document' && !data.demo) renderDocumentOverview(data, overview);
  if (['media','offer'].includes(data.module_type) && !data.demo) renderMediaOfferOverview(data,overview);
  renderPlainResult(data, overview);
  document.getElementById('evidencePolicyDisclaimer').textContent = data.demo ? 'Illustrative sample only. No uploaded content was analyzed and no live reputation, OCR, or authenticity check was performed.' : 'SafeLens combines heuristic rules, DNS verification, and local machine learning to identify risks. Missing or inconclusive checks are explicitly reported.';

  if (timestamp) {
    try {
      const dt = new Date(data.created_at_iso || data.created_at);
      timestamp.textContent = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' · ' + dt.toLocaleDateString();
    } catch {
      timestamp.textContent = 'Just now';
    }
  }

  // Risk badge styling
  if (riskBadge) {
    riskBadge.className = 'item-status-badge';
    const risk = data.risk_category || 'Unable to Assess';
    riskBadge.textContent = {'High Risk':'High risk','Caution':'Be careful','Low Risk':'Few warning signs','Unable to Assess':'Incomplete check'}[risk] || risk;

    if (risk === 'High Risk') {
      riskBadge.classList.add('badge-high-risk');
    } else if (risk === 'Caution') {
      riskBadge.classList.add('badge-caution');
    } else if (risk === 'Low Risk') {
      riskBadge.classList.add('badge-low-risk');
    } else {
      riskBadge.classList.add('badge-unable');
    }
  }

  // Tab 1: Findings
  const findingsContainer = document.getElementById('findingsContainer');
  const findingsCount = document.getElementById('findingsCount');
  if (findingsCount) findingsCount.textContent = (data.findings || []).length;

  if (findingsContainer) {
    findingsContainer.innerHTML = '';

    if (!data.findings || data.findings.length === 0) {
      findingsContainer.innerHTML = `
        <div style="padding: 20px; text-align: center; color: #64748b; font-size: 13.5px;">
          ${['screenshot', 'message', 'qr', 'document', 'media', 'offer'].includes(data.module_type) ? 'No grounded findings are available in this view. Review checks and limitations; absent evidence does not establish safety.' : 'No explicit threat anomalies detected in submitted content.'}
        </div>
      `;
    } else {
      data.findings.forEach((f) => {
        const card = document.createElement('div');
        card.className = 'finding-card';
        card.innerHTML = `
          <div class="finding-header">
            <span class="finding-source-tag">${escapeHtml(f.source)}${f.timestamp_seconds!=null?' · '+Number(f.timestamp_seconds).toFixed(2)+'s':''}${f.reference ? ' · ' + escapeHtml(f.reference) : f.page_number ? ' · Page ' + f.page_number : ''}</span>
            <span class="status-pill status-${f.risk_level === 'High Risk' ? 'flagged' : (f.risk_level === 'Caution' ? 'hops' : 'low-risk')}">${escapeHtml(f.risk_level)}</span>
          </div>
          <div class="finding-obs">${escapeHtml(f.observation)}</div>
          <div class="finding-interp">${escapeHtml(f.interpretation)}</div>
          <div class="finding-action">Recommended action: ${escapeHtml(f.action)}</div>
        `;
        findingsContainer.appendChild(card);
      });
    }

    // Render Evidence Excerpts if available
    if (data.evidence && data.evidence.length > 0) {
      const evHeader = document.createElement('h5');
      evHeader.style.cssText = 'font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin: 20px 0 10px 0;';
      evHeader.textContent = 'Content Excerpts & Visual Clues';
      findingsContainer.appendChild(evHeader);

      data.evidence.forEach((ev) => {
        const evBox = document.createElement('div');
        evBox.className = 'url-excerpt-box';
        evBox.style.marginBottom = '10px';
        evBox.innerHTML = `
          <span style="font-size: 11px; font-weight: 700; color: #0d9488; text-transform: uppercase; display: block; margin-bottom: 4px;">Source: ${escapeHtml(ev.source_type)} ${ev.timestamp_seconds!=null?Number(ev.timestamp_seconds).toFixed(2)+'s':''} ${ev.page_number ? `(Page ${ev.page_number})` : ev.reference ? escapeHtml(ev.reference) : ''}</span>
          <code>${escapeHtml(ev.snippet)}</code>
          ${ev.detail ? `<div style="font-size: 12px; color: #64748b; margin-top: 4px;">${escapeHtml(ev.detail)}</div>` : ''}
        `;
        findingsContainer.appendChild(evBox);
      });
    }
  }

  // Tab 2: Checks Status
  const checksContainer = document.getElementById('checksListContainer');
  const checksCount = document.getElementById('checksCount');
  const totalChecks = (data.checks_performed || []).length + (data.unavailable_checks || []).length;
  if (checksCount) checksCount.textContent = totalChecks;

  if (checksContainer) {
    checksContainer.innerHTML = '';

    (data.checks_performed || []).forEach((c) => {
      const row = document.createElement('div');
      row.className = 'check-status-row';
      const isPassed = c.status === 'passed';
      const isFlagged = c.status === 'flagged';
      row.innerHTML = `
        <div class="check-row-left">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="${isPassed ? '#0d9488' : (isFlagged ? '#ef4444' : '#f59e0b')}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            ${isPassed ? '<circle cx="12" cy="12" r="10"/><polyline points="16 10 11 15 8 12"/>' : (isFlagged ? '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>' : '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>')}
          </svg>
          <span class="check-name">${escapeHtml(c.name)}</span>
        </div>
        <span class="status-pill status-${isFlagged ? 'flagged' : (isPassed ? 'low-risk' : 'hops')}">${escapeHtml(c.detail)}</span>
      `;
      checksContainer.appendChild(row);
    });

    (data.unavailable_checks || []).forEach((c) => {
      const row = document.createElement('div');
      row.className = 'check-status-row';
      row.innerHTML = `
        <div class="check-row-left">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span class="check-name" style="color: #64748b;">${escapeHtml(c.name)}</span>
        </div>
        <span class="status-text-inconclusive" style="font-size: 11.5px; color: #94a3b8;">${escapeHtml(c.detail)}</span>
      `;
      checksContainer.appendChild(row);
    });
  }

  // Tab 3: Safeguards
  const safeguardsList = document.getElementById('safeguardsList');
  if (safeguardsList) {
    safeguardsList.innerHTML = '';
    (data.recommended_actions || []).forEach((act) => {
      const li = document.createElement('li');
      li.innerHTML = `
        <span class="red-bullet"></span>
        <span>${escapeHtml(act)}</span>
      `;
      safeguardsList.appendChild(li);
    });
  }

  // Copy Destination Button
  const btnCopy = document.getElementById('btnCopyDestination');
  if (btnCopy) {
    if (data.module_type === 'link') {
      btnCopy.style.display = 'inline-flex';
      btnCopy.onclick = () => {
        const textToCopy = data.input_summary || '';
        navigator.clipboard.writeText(textToCopy).then(() => {
          showToast(`Copied destination to clipboard`);
        });
      };
    } else {
      btnCopy.style.display = 'none';
    }
  }

  // Check Another Button
  const btnCheckAnother = document.getElementById('btnCheckAnother');
  if (btnCheckAnother) {
    btnCheckAnother.onclick = () => {
      const modal = document.getElementById('contactModal');
      if (modal) {
        setModalModule(data.module_type);
        if (['message','offer'].includes(data.module_type)) {
          document.getElementById('inputTextField').value = '';
          updateMessageCount();
        }
        if (['screenshot','qr','document','media','offer'].includes(data.module_type)) clearScreenshotInput();
        modal.classList.add('open');
      }
    };
  }
}

async function loadAssessmentById(assessmentId) {
  try {
    const res = await fetch(`/api/assessments/${encodeURIComponent(assessmentId)}`);
    if (!res.ok) {
      showToast('Assessment not found or expired');
      return;
    }
    const data = await res.json();
    renderAssessment(data);
    const archSec = document.getElementById('architecture');
    if (archSec) archSec.scrollIntoView({ behavior: 'smooth' });
  } catch (err) {
    console.error('Failed to load assessment:', err);
    showToast('Failed to retrieve assessment');
  }
}

/* --------------------------------------------------------------------------
   9. SESSION TELEMETRY & DASHBOARD HISTORY
   -------------------------------------------------------------------------- */
async function loadDashboardData() {
  try {
    // 1. Telemetry Summary
    const sumRes = await fetch('/api/dashboard/summary');
    if (sumRes.ok) {
      const sumData = await sumRes.json();
      const elTotal = document.getElementById('telemetryTotal');
      const elCaution = document.getElementById('telemetryCaution');
      const elHigh = document.getElementById('telemetryHighRisk');
      if (elTotal) elTotal.textContent = sumData.total_assessments ?? 0;
      if (elCaution) elCaution.textContent = sumData.caution_count ?? 0;
      if (elHigh) elHigh.textContent = sumData.high_risk_count ?? 0;
    }

    // 2. History List
    const histRes = await fetch('/api/history');
    if (histRes.ok) {
      const items = await histRes.json();
      const listContainer = document.getElementById('recentAssessmentsList');
      const placeholder = document.getElementById('historyEmptyPlaceholder');
      const clearBtn = document.getElementById('btnClearHistory');
      const badgeCount = document.getElementById('historyCountBadge');

      if (badgeCount) badgeCount.textContent = items.length;

      if (!items || items.length === 0) {
        if (placeholder) placeholder.style.display = 'block';
        if (clearBtn) clearBtn.style.display = 'none';
        if (listContainer) {
          listContainer.innerHTML = '';
          if (placeholder) listContainer.appendChild(placeholder);
        }
      } else {
        if (placeholder) placeholder.style.display = 'none';
        if (clearBtn) clearBtn.style.display = 'inline-block';
        if (listContainer) {
          listContainer.innerHTML = '';
          items.forEach((item) => {
            const row = document.createElement('div');
            row.className = 'assessment-item';

            let badgeClass = 'badge-unable';
            if (item.risk_category === 'High Risk') badgeClass = 'badge-high-risk';
            else if (item.risk_category === 'Caution') badgeClass = 'badge-caution';
            else if (item.risk_category === 'Low Risk') badgeClass = 'badge-low-risk';

            row.innerHTML = `
              <div class="item-left-block">
                <span class="intake-type-pill">${escapeHtml((item.module_type || 'CHECK').toUpperCase())}</span>
                <div class="item-title-block">
                  <h4 class="item-filename">${escapeHtml(item.input_summary || 'Untitled check')}</h4>
                  <span class="item-timestamp">${formatRelativeTime(item.created_at)}</span>
                </div>
              </div>
              <div class="item-right-block">
                <span class="item-status-badge ${badgeClass}">${escapeHtml(item.risk_category)}</span>
                <svg class="item-chevron" viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </div>
            `;

            row.addEventListener('click', () => {
              window.location.hash = `#/results/${item.id}`;
            });

            listContainer.appendChild(row);
          });
        }
      }
    }
  } catch (err) {
    console.error('Failed to load dashboard data:', err);
  }
}

async function clearSessionHistory() {
  if (!confirm('Clear all session history records? This action permanently purges your local activity.')) return;
  try {
    const res = await fetch('/api/history', { method: 'DELETE' });
    if (res.ok) {
      showToast('Session history successfully purged');
      loadDashboardData();

      // Reset evidence display if showing a cleared assessment
      const emptyState = document.getElementById('evidenceEmptyState');
      const activeState = document.getElementById('evidenceActiveState');
      if (emptyState) emptyState.style.display = 'flex';
      if (activeState) activeState.style.display = 'none';
    }
  } catch (err) {
    console.error('Failed to clear history:', err);
    showToast('Failed to clear history');
  }
}

/* --------------------------------------------------------------------------
   10. CLIENT-SIDE ROUTER & TABS
   -------------------------------------------------------------------------- */
function initRouter() {
  function handleRoute() {
    const hash = window.location.hash || '#/';

    if (hash.startsWith('#/check/')) {
      const moduleType = hash.replace('#/check/', '');
      const modal = document.getElementById('contactModal');
      if (modal) {
        setModalModule(moduleType);
        modal.classList.add('open');
      }
    } else if (hash.startsWith('#/results/')) {
      const id = hash.replace('#/results/', '');
      if (id.startsWith('demo-')) {
        const moduleType = id.slice(5);
        if (['link', 'message', 'screenshot', 'qr', 'document', 'media', 'offer'].includes(moduleType)) {
          setModalModule(moduleType);
          document.getElementById('contactModal').classList.add('open');
        } else if (Object.hasOwn(moduleExperiences, moduleType)) {
          activeModule = moduleType;
          if (currentAssessment?.id !== id) reviewModuleSample();
        }
      } else if (id) loadAssessmentById(id);
    } else if (hash === '#/dashboard' || hash === '#/history') {
      const histSec = document.getElementById('history');
      if (histSec) histSec.scrollIntoView({ behavior: 'smooth' });
    } else if (hash === '#/help') {
      const procSec = document.getElementById('process');
      if (procSec) procSec.scrollIntoView({ behavior: 'smooth' });
    }
  }

  window.addEventListener('hashchange', handleRoute);
  // Initial route handle
  handleRoute();
}

function initEvidenceTabs() {
  const tabBtns = document.querySelectorAll('.evidence-tab-btn');
  tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetTabId = btn.getAttribute('data-tab');
      tabBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      const panes = document.querySelectorAll('.evidence-tab-pane');
      panes.forEach((pane) => {
        if (pane.id === targetTabId) {
          pane.classList.add('active');
        } else {
          pane.classList.remove('active');
        }
      });
    });
  });

  const btnClearHist = document.getElementById('btnClearHistory');
  if (btnClearHist) {
    btnClearHist.addEventListener('click', clearSessionHistory);
  }
}

/* --------------------------------------------------------------------------
   HELPERS
   -------------------------------------------------------------------------- */
function showToast(msg) {
  const toast = document.getElementById('toastNotification');
  const msgEl = document.getElementById('toastMessage');
  if (!toast || !msgEl) return;
  msgEl.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3200);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return 'Recently';
  try {
    const dt = new Date(dateStr);
    return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' · ' + dt.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

