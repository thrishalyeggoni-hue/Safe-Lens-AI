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
   1. CUSTOM MAGNETIC CURSOR (DEAD CENTER ALIGNMENT)
   -------------------------------------------------------------------------- */
function initCustomCursor() {
  const cursor = document.getElementById('customCursor');
  const follower = document.getElementById('cursorFollower');
  if (!cursor || !follower) return;

  let mouseX = window.innerWidth / 2;
  let mouseY = window.innerHeight / 2;
  let followerX = mouseX;
  let followerY = mouseY;
  let isVisible = false;

  window.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;

    if (!isVisible) {
      isVisible = true;
      cursor.style.opacity = '1';
      follower.style.opacity = '1';
    }

    // Dot represents INSTANTANEOUS mouse coordinate, centered with translate(-50%, -50%)
    cursor.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0) translate(-50%, -50%)`;

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
  });

  window.addEventListener('mouseleave', () => {
    cursor.style.opacity = '0';
    follower.style.opacity = '0';
    isVisible = false;
  });

  function renderCursor() {
    // Follower smoothly eases toward mouse position with spring physics
    followerX += (mouseX - followerX) * 0.18;
    followerY += (mouseY - followerY) * 0.18;

    // Follower also centered with translate(-50%, -50%), guaranteeing the dot is DEAD CENTER
    follower.style.transform = `translate3d(${followerX}px, ${followerY}px, 0) translate(-50%, -50%)`;
    requestAnimationFrame(renderCursor);
  }
  requestAnimationFrame(renderCursor);

  // Magnetic & Hover expansion over interactive elements
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

function setModalModule(moduleType) {
  activeModule = moduleType || 'link';
  
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
      if (modalSub) modalSub.textContent = 'Inspect redirect hops, lookalike homoglyphs, DNS records, and threat reputation.';
      if (groupUrl) groupUrl.style.display = 'flex';
      if (groupText) groupText.style.display = 'none';
      if (groupFile) groupFile.style.display = 'none';
      if (urlInput) urlInput.placeholder = 'https://suspicious-pay-login.com/auth';
      break;

    case 'message':
      if (modalTitle) modalTitle.textContent = 'Message Check — Read Between the Lines';
      if (modalSub) modalSub.textContent = 'Analyze urgent SMS, chat, or WhatsApp lures for OTP harvesting and advance fee traps.';
      if (groupUrl) groupUrl.style.display = 'none';
      if (groupText) groupText.style.display = 'flex';
      if (groupFile) groupFile.style.display = 'none';
      if (textInput) textInput.placeholder = 'Paste urgent message text, e.g. "Your bank account has been suspended! Verify immediately at..."';
      break;

    case 'screenshot':
      if (modalTitle) modalTitle.textContent = 'Screenshot Check — See Hidden Clues';
      if (modalSub) modalSub.textContent = 'Optical character recognition (OCR) and layout inspection for payment slips & lures.';
      if (groupUrl) groupUrl.style.display = 'none';
      if (groupText) groupText.style.display = 'none';
      if (groupFile) groupFile.style.display = 'flex';
      if (fileLabel) fileLabel.textContent = 'Screenshot / Image Upload (PNG, JPG, WEBP)';
      if (fileInput) fileInput.accept = 'image/*';
      if (dropHint) dropHint.textContent = 'Supports PNG, JPG, WEBP up to 50MB';
      break;

    case 'qr':
      if (modalTitle) modalTitle.textContent = 'QR Check — Know Where It Leads';
      if (modalSub) modalSub.textContent = 'Decode barcode matrices, inspect target URLs, and parse UPI payment identifiers.';
      if (groupUrl) groupUrl.style.display = 'flex';
      if (groupText) groupText.style.display = 'none';
      if (groupFile) groupFile.style.display = 'flex';
      if (urlInput) urlInput.placeholder = 'Or enter decoded QR text / URL directly...';
      if (fileLabel) fileLabel.textContent = 'QR Code Image (PNG, JPG)';
      if (fileInput) fileInput.accept = 'image/*';
      if (dropHint) dropHint.textContent = 'Upload image containing one or more QR codes';
      break;

    case 'document':
      if (modalTitle) modalTitle.textContent = 'Document Check — Check the Fine Print';
      if (modalSub) modalSub.textContent = 'Deep PDF inspection: embedded launch actions, links, payment tables, and structure.';
      if (groupUrl) groupUrl.style.display = 'none';
      if (groupText) groupText.style.display = 'none';
      if (groupFile) groupFile.style.display = 'flex';
      if (fileLabel) fileLabel.textContent = 'PDF Document';
      if (fileInput) fileInput.accept = '.pdf,application/pdf';
      if (dropHint) dropHint.textContent = 'Supports PDF documents up to 50MB (max 30 pages)';
      break;

    case 'media':
      if (modalTitle) modalTitle.textContent = 'Media Check — Look Beyond the Surface';
      if (modalSub) modalSub.textContent = 'Container metadata inspection, keyframe sampling, OCR, and speech transcription readiness.';
      if (groupUrl) groupUrl.style.display = 'none';
      if (groupText) groupText.style.display = 'none';
      if (groupFile) groupFile.style.display = 'flex';
      if (fileLabel) fileLabel.textContent = 'Video or Audio File';
      if (fileInput) fileInput.accept = 'video/*,audio/*,image/*';
      if (dropHint) dropHint.textContent = 'Supports MP4, WebM, MOV, MP3 up to 50MB';
      break;

    case 'offer':
      if (modalTitle) modalTitle.textContent = 'Offer Check — Pause Before the Promise';
      if (modalSub) modalSub.textContent = 'Analyze job postings, tasks, and guaranteed return pitches for advance payment traps.';
      if (groupUrl) groupUrl.style.display = 'none';
      if (groupText) groupText.style.display = 'flex';
      if (groupFile) groupFile.style.display = 'flex';
      if (textInput) textInput.placeholder = 'Paste offer description, e.g. "Work from home part time, earn ₹50,000/day rating hotels. Deposit ₹500 to activate..."';
      if (fileLabel) fileLabel.textContent = 'Optional Offer PDF Attachment';
      if (fileInput) fileInput.accept = '.pdf,application/pdf';
      if (dropHint) dropHint.textContent = 'Optional PDF offer brochure or contract';
      break;
  }
}

function initCardsInteractions() {
  const serviceCards = document.querySelectorAll('.stepped-threat-card');
  const modal = document.getElementById('contactModal');

  serviceCards.forEach((card) => {
    card.addEventListener('click', () => {
      const serviceType = card.getAttribute('data-service') || 'link';
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
function initModalInteractions() {
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
    activeSelectedFile = file;
    if (selectedFileName) selectedFileName.textContent = file.name;
    if (fileSelectedInfo) fileSelectedInfo.style.display = 'flex';
    if (dropzonePrompt) dropzonePrompt.style.display = 'none';
  }

  if (btnRemoveFile) {
    btnRemoveFile.addEventListener('click', (e) => {
      e.stopPropagation();
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
      const textVal = document.getElementById('inputTextField')?.value.trim() || '';

      // Validation
      if (activeModule === 'link' && !urlVal) {
        showToast('Please enter a target URL or domain');
        return;
      }
      if (activeModule === 'message' && !textVal) {
        showToast('Please enter message text to inspect');
        return;
      }
      if (['screenshot', 'document', 'media'].includes(activeModule) && !activeSelectedFile) {
        showToast('Please select or upload a file for analysis');
        return;
      }
      if (activeModule === 'qr' && !activeSelectedFile && !urlVal) {
        showToast('Please upload a QR image or enter matrix text');
        return;
      }

      const overlay = document.getElementById('processingOverlay');
      const stageText = document.getElementById('processingStageText');
      const stageSub = document.getElementById('processingStageSub');

      if (overlay) overlay.classList.add('active');
      if (stageText) stageText.textContent = 'Validating input & structure...';
      if (stageSub) stageSub.textContent = 'Step 1 of 4: Content format and bounds verification';

      activeAbortController = new AbortController();

      try {
        let response;
        if (activeSelectedFile) {
          const formData = new FormData();
          formData.append('module_type', activeModule);
          formData.append('file', activeSelectedFile);
          if (textVal) formData.append('content_text', textVal);
          if (urlVal) formData.append('target_url', urlVal);

          // Simulated intermediate real-stage updates
          setTimeout(() => {
            if (stageText) stageText.textContent = 'Extracting content & machine-readable data...';
            if (stageSub) stageSub.textContent = 'Step 2 of 4: Optical recognition / parsing active';
          }, 350);

          setTimeout(() => {
            if (stageText) stageText.textContent = 'Running threat intelligence & heuristics...';
            if (stageSub) stageSub.textContent = 'Step 3 of 4: DNS, reputation and pattern checking';
          }, 700);

          response = await fetch('/api/assessments', {
            method: 'POST',
            body: formData,
            signal: activeAbortController.signal,
          });
        } else {
          setTimeout(() => {
            if (stageText) stageText.textContent = 'Executing DNS resolution & network trace...';
            if (stageSub) stageSub.textContent = 'Step 2 of 4: Reputation & heuristic checks';
          }, 350);

          setTimeout(() => {
            if (stageText) stageText.textContent = 'Synthesizing evidence & risk assessment...';
            if (stageSub) stageSub.textContent = 'Step 3 of 4: Determining policy verdict';
          }, 700);

          response = await fetch('/api/assessments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              module_type: activeModule,
              content_text: textVal,
              target_url: urlVal,
            }),
            signal: activeAbortController.signal,
          });
        }

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Server error (${response.status})`);
        }

        const assessmentData = await response.json();
        
        // Success
        closeModal();
        renderAssessment(assessmentData);
        window.location.hash = `#/results/${assessmentData.id}`;
        
        // Scroll to evidence section
        const archSec = document.getElementById('architecture');
        if (archSec) archSec.scrollIntoView({ behavior: 'smooth' });

        // Update dashboard telemetry and history
        loadDashboardData();
        showToast('Assessment completed successfully');
      } catch (err) {
        if (err.name === 'AbortError') return;
        console.error('Assessment failed:', err);
        if (stageText) stageText.textContent = 'Assessment Error';
        if (stageSub) stageSub.textContent = err.message || 'An unexpected error occurred during processing.';
        showToast(`Error: ${err.message || 'Scan failed'}`);
      } finally {
        activeAbortController = null;
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
function renderAssessment(data) {
  currentAssessment = data;
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
  if (title) title.textContent = `${(data.module_type || 'Threat').toUpperCase()} Assessment`;
  if (inputSummary) inputSummary.textContent = data.input_summary || 'Submitted content';
  
  if (timestamp) {
    try {
      const dt = new Date(data.created_at);
      timestamp.textContent = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' · ' + dt.toLocaleDateString();
    } catch {
      timestamp.textContent = 'Just now';
    }
  }

  // Risk badge styling
  if (riskBadge) {
    riskBadge.className = 'item-status-badge';
    const risk = data.risk_category || 'Unable to Assess';
    riskBadge.textContent = risk;

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
          No explicit threat anomalies detected in submitted content.
        </div>
      `;
    } else {
      data.findings.forEach((f) => {
        const card = document.createElement('div');
        card.className = 'finding-card';
        card.innerHTML = `
          <div class="finding-header">
            <span class="finding-source-tag">${escapeHtml(f.source)}</span>
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
          <span style="font-size: 11px; font-weight: 700; color: #0d9488; text-transform: uppercase; display: block; margin-bottom: 4px;">Source: ${escapeHtml(ev.source_type)} ${ev.page_number ? `(Page ${ev.page_number})` : ''}</span>
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
    if (['link', 'qr'].includes(data.module_type)) {
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
      if (id) loadAssessmentById(id);
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

