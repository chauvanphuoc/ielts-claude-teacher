/* ── IELTS Studio — Application Logic ── */

const BRIDGE_URL = 'http://localhost:8765';

/* ── State ── */
let currentMode = 'speaking';
let isRecording = false;
let mediaRecorder = null;
let recognition = null;
let speakingTimer = null;
let speakingSeconds = 0;
let transcript = '';
let audioChunks = [];       // collected audio data from MediaRecorder
let audioBlob = null;       // final blob after recording stops
let currentAudioMimeType = 'audio/webm';
let roadmap = null;
let currentTestData = null;  // loaded JSON test data
let currentTestSource = 'cambridge-1';
let currentTestNumber = 1;
let speakingTaskData = null;   // loaded speaking JSON
let currentSpeakingPart = 1;   // 1, 2, or 3
let speakingSources = [];      // available speaking sources from /api/speaking/

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  setupModeTabs();
  setupSpeaking();
  setupListening();
  setupWriting();
  setupReading();
  loadRoadmap();
  checkBridge();
  setupKeyboardNav();
});

/* ── Bridge Check ── */
async function checkBridge() {
  try {
    const r = await fetch(BRIDGE_URL + '/save', { method: 'OPTIONS' });
    document.getElementById('status-band').textContent = 'Bridge: connected';
  } catch(e) {
    document.getElementById('status-band').textContent = 'Bridge: not running';
  }
}

/* ── Roadmap ── */
async function loadRoadmap() {
  try {
    const r = await fetch(BRIDGE_URL + '/roadmap.json');
    if (r.ok) {
      roadmap = await r.json();
      renderRoadmap();
    } else {
      showRoadmapEmpty();
    }
  } catch(e) {
    document.getElementById('roadmap-loading').style.display = 'none';
    document.getElementById('roadmap-empty').style.display = 'block';
  }
}

function renderRoadmap() {
  if (!roadmap || !roadmap.skills) { showRoadmapEmpty(); return; }
  document.getElementById('roadmap-loading').style.display = 'none';
  document.getElementById('roadmap-content').style.display = 'block';

  const activeSkills = roadmap.learner?.activeSkills || ['writing','reading','listening','speaking'];
  const skills = roadmap.skills;
  const bands = Object.values(skills).filter(s => s.currentBand > 0).map(s => s.currentBand);
  const overall = bands.length ? (bands.reduce((a,b) => a + b, 0) / bands.length).toFixed(1) : '--';

  document.getElementById('overall-band').textContent = overall;
  document.getElementById('target-info').textContent =
    `Target: Band ${roadmap.learner?.targetBand || '?'} | ${roadmap.learner?.examDate || 'No exam date'}`;

  const bars = document.getElementById('skill-bars');
  bars.innerHTML = '';
  const skillNames = { writing: 'Writing', reading: 'Reading', listening: 'Listening', speaking: 'Speaking' };
  for (const [key, name] of Object.entries(skillNames)) {
    const skill = skills[key];
    const active = activeSkills.includes(key);
    const band = skill?.currentBand || 0;
    const pct = Math.min(100, (band / 9.0) * 100);
    const cls = !active ? 'inactive' : (band < (roadmap.learner?.targetBand || 7) - 1 ? 'warning' : '');

    bars.innerHTML += `
      <div class="band-bar ${!active ? 'inactive' : ''}">
        <div class="label"><span>${name} ${!active ? '(skipped)' : ''}</span><span>${band > 0 ? band.toFixed(1) : '--'}</span></div>
        <div class="track"><div class="fill ${cls}" style="width:${pct}%"></div></div>
      </div>`;
  }

  const weakList = document.getElementById('weak-list');
  weakList.innerHTML = '';
  for (const [key, skill] of Object.entries(skills)) {
    if (skill.weakAreas) {
      skill.weakAreas.forEach(w => {
        weakList.innerHTML += `<li>${skillNames[key]}: ${w.tag} (${Math.round(w.errorRate*100)}%)</li>`;
      });
    }
  }
  if (!weakList.innerHTML) weakList.innerHTML = '<li style="color:#888">No weak areas yet</li>';
}

function showRoadmapEmpty() {
  document.getElementById('roadmap-loading').style.display = 'none';
  document.getElementById('roadmap-empty').style.display = 'block';
}

/* ── Mode Tabs ── */
function setupModeTabs() {
  document.querySelectorAll('#mode-tabs button').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#mode-tabs button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      switchMode(btn.dataset.mode);
    });
  });
}

function switchMode(mode) {
  currentMode = mode;
  document.getElementById('panel-speaking').style.display = mode === 'speaking' ? '' : 'none';
  document.getElementById('panel-listening').style.display = mode === 'listening' ? '' : 'none';
  document.getElementById('panel-writing').style.display = mode === 'writing' ? '' : 'none';
  document.getElementById('panel-reading').style.display = mode === 'reading' ? '' : 'none';
  document.getElementById('status-text').textContent = mode.charAt(0).toUpperCase() + mode.slice(1) + ' mode';
  if (mode === 'speaking' && !speakingTaskData) loadSpeakingSources();
}

/* ── Shared Save Helper ── */
async function saveResult(data) {
  try {
    const r = await fetch(BRIDGE_URL + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!r.ok) throw new Error('Save failed: ' + r.status);
    return { ok: true };
  } catch(e) {
    const skill = data.skill || 'unknown';
    const el = document.getElementById(skill + '-error');
    if (el) {
      el.style.display = 'block';
      el.textContent = 'Failed to save. Is the bridge server running? Check Claude and say "/ielts-check".';
    }
    return { ok: false, error: e };
  }
}

/* ── Speaking ── */
function setupSpeaking() {
  const btn = document.getElementById('record-btn');
  const submit = document.getElementById('speaking-submit');
  btn.addEventListener('click', () => {
    if (isRecording) stopRecording();
    else startRecording();
  });
  submit.addEventListener('click', saveSpeaking);

  // Task selector
  document.getElementById('speaking-source').addEventListener('change', onSourceChange);
  document.getElementById('speaking-test').addEventListener('change', onTestChange);

  // Part navigation — click + keyboard
  const partNav = document.getElementById('part-nav');
  partNav.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-part]');
    if (btn) selectSpeakingPart(parseInt(btn.dataset.part));
  });
  partNav.addEventListener('keydown', (e) => {
    const btns = [...partNav.querySelectorAll('button[data-part]')];
    const idx = btns.indexOf(document.activeElement);
    if (e.key === 'ArrowRight' && idx < btns.length - 1) { btns[idx + 1].focus(); e.preventDefault(); }
    if (e.key === 'ArrowLeft' && idx > 0) { btns[idx - 1].focus(); e.preventDefault(); }
  });
}

/* ── Speaking: Task Loading ── */
async function loadSpeakingSources() {
  const sourceSelect = document.getElementById('speaking-source');
  sourceSelect.innerHTML = '<option value="">-- Loading... --</option>';
  sourceSelect.disabled = true;

  try {
    const r = await fetch(BRIDGE_URL + '/api/speaking/');
    if (!r.ok) throw new Error('API error: ' + r.status);
    const data = await r.json();
    speakingSources = data.sources || [];

    if (speakingSources.length === 0) {
      showSpeakingEmpty();
      return;
    }

    sourceSelect.innerHTML = speakingSources.map(s =>
      `<option value="${s.id}">${s.id}</option>`
    ).join('');
    sourceSelect.disabled = false;

    // Auto-select first source and load it
    sourceSelect.value = speakingSources[0].id;
    onSourceChange();
  } catch (e) {
    showSpeakingError('Failed to load speaking sources. Is the bridge server running?',
      () => loadSpeakingSources());
    sourceSelect.innerHTML = '<option value="">-- Error --</option>';
    sourceSelect.disabled = true;
  }
}

function showSpeakingEmpty() {
  document.getElementById('speaking-selector').style.display = '';
  document.getElementById('speaking-source').innerHTML = '<option value="">-- No sources --</option>';
  document.getElementById('speaking-source').disabled = true;
  document.getElementById('cue-card').style.display = 'none';
  document.getElementById('part-nav').style.display = 'none';
  document.getElementById('speaking-empty').style.display = '';
  document.getElementById('speaking-active').style.display = 'none';
  document.getElementById('speaking-success').style.display = 'none';
}

function showSpeakingError(msg, retryFn) {
  const card = document.getElementById('cue-card');
  card.style.display = '';
  card.className = 'cue-card error-card';
  card.innerHTML = `
    <p>&#x26A0; ${msg}</p>
    ${retryFn ? '<button class="retry-btn">Retry</button>' : ''}
  `;
  if (retryFn) card.querySelector('.retry-btn').addEventListener('click', retryFn);
  document.getElementById('part-nav').style.display = 'none';
  document.getElementById('speaking-active').style.display = 'block';
  document.getElementById('speaking-empty').style.display = 'none';
  document.getElementById('speaking-success').style.display = 'none';
  document.getElementById('speaking-error').style.display = 'none';
}

async function onSourceChange() {
  const sourceId = document.getElementById('speaking-source').value;
  if (!sourceId) return;

  const testSelect = document.getElementById('speaking-test');
  testSelect.innerHTML = '<option value="">-- Loading... --</option>';
  testSelect.disabled = true;

  // Show loading in cue card
  const card = document.getElementById('cue-card');
  card.style.display = '';
  card.className = 'cue-card loading-card';
  card.innerHTML = 'Loading task...';
  document.getElementById('part-nav').style.display = 'none';
  document.getElementById('speaking-empty').style.display = 'none';
  document.getElementById('speaking-success').style.display = 'none';
  document.getElementById('speaking-error').style.display = 'none';

  try {
    const r = await fetch(BRIDGE_URL + '/api/speaking/' + sourceId);
    if (!r.ok) throw new Error('Source not found: ' + r.status);
    speakingTaskData = await r.json();

    const tests = speakingTaskData.tests || [];
    testSelect.innerHTML = tests.map(t =>
      `<option value="${t.testNumber}">Test ${t.testNumber}</option>`
    ).join('');
    testSelect.disabled = false;

    // Auto-select first test
    testSelect.value = tests[0].testNumber;
    onTestChange();
  } catch (e) {
    showSpeakingError('Failed to load tasks for ' + sourceId + '. Is the bridge server running?',
      () => onSourceChange());
    testSelect.innerHTML = '<option value="">-- Error --</option>';
    testSelect.disabled = true;
  }
}

function onTestChange() {
  const testNum = parseInt(document.getElementById('speaking-test').value);
  if (!testNum || !speakingTaskData) return;

  const test = speakingTaskData.tests.find(t => t.testNumber === testNum);
  if (!test) return;

  // Store test reference for rendering
  currentTestSource = document.getElementById('speaking-source').value;
  currentTestNumber = testNum;

  // Show part nav and cue card
  document.getElementById('part-nav').style.display = '';
  document.getElementById('cue-card').style.display = '';
  document.getElementById('cue-card').className = 'cue-card';
  document.getElementById('speaking-empty').style.display = 'none';
  document.getElementById('speaking-error').style.display = 'none';
  document.getElementById('speaking-success').style.display = 'none';

  // Auto-select Part 1
  selectSpeakingPart(1);
}

function selectSpeakingPart(partNum) {
  if (!speakingTaskData) return;
  const test = speakingTaskData.tests.find(t => t.testNumber === currentTestNumber);
  if (!test) return;

  const part = test.parts.find(p => p.partNumber === partNum);
  if (!part) return;

  currentSpeakingPart = partNum;
  renderSpeakingPart(part);

  // Update pill active state
  const partNav = document.getElementById('part-nav');
  partNav.querySelectorAll('button[data-part]').forEach(btn => {
    const isActive = parseInt(btn.dataset.part) === partNum;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });

  // Show recording UI if not already visible
  if (document.getElementById('speaking-active').style.display === 'none') {
    document.getElementById('speaking-active').style.display = '';
  }
}

function renderSpeakingPart(part) {
  const card = document.getElementById('cue-card');
  card.className = 'cue-card';

  if (part.partType === 'interview') {
    card.innerHTML = `
      <div class="card-title">${part.topic}</div>
      <div class="card-scenario">${part.instructions}</div>
      <ol class="card-questions">
        ${part.questions.map((q, i) => `<li><span class="q-num">${i + 1}.</span>${q}</li>`).join('')}
      </ol>
    `;
  } else if (part.partType === 'long-turn') {
    const cc = part.cueCard;
    card.innerHTML = `
      <div class="card-title">${cc.topic}</div>
      <div class="card-scenario">You have ${part.preparationTime} second${part.preparationTime !== 1 ? 's' : ''} to prepare and up to ${Math.floor(part.speakingTime / 60)} minute${part.speakingTime > 60 ? 's' : ''} to speak.</div>
      <div class="card-role">Take one minute to prepare. Make notes if you wish.</div>
      <div class="card-topics-label">You should say:</div>
      <ul class="card-topics">
        ${cc.bullets.map(b => `<li>${b}</li>`).join('')}
      </ul>
    `;
  } else if (part.partType === 'discussion') {
    card.innerHTML = `
      <div class="card-title">${part.topic}</div>
      <div class="card-scenario">Discuss these questions related to the Part 2 topic.</div>
      <ol class="card-questions">
        ${part.questions.map((q, i) => `<li><span class="q-num">${i + 1}.</span>${q}</li>`).join('')}
      </ol>
    `;
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';
      recognition.onresult = (e) => {
        transcript = '';
        for (let i = 0; i < e.results.length; i++) {
          transcript += e.results[i][0].transcript + ' ';
        }
        document.getElementById('speaking-transcript').textContent = transcript || 'Listening...';
      };
      recognition.onerror = (e) => {
        if (e.error !== 'no-speech') {
          document.getElementById('speaking-transcript').textContent =
            `[Speech recognition error: ${e.error}. Continue speaking — your audio is still being recorded.]`;
        }
      };
      recognition.start();
    }
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    audioBlob = null;
    currentAudioMimeType = mediaRecorder.mimeType || 'audio/webm';
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      if (audioChunks.length > 0) {
        audioBlob = new Blob(audioChunks, { type: currentAudioMimeType });
      }
    };
    mediaRecorder.start();

    isRecording = true;
    document.getElementById('record-btn').classList.add('recording');
    document.querySelector('.speaking-container')?.classList.add('recording');
    document.getElementById('speaking-empty').style.display = 'none';
    document.getElementById('speaking-active').style.display = '';
    document.getElementById('speaking-success').style.display = 'none';
    // Keep cue card + selector + part nav visible during recording
    document.getElementById('speaking-selector').style.display = '';
    document.getElementById('cue-card').style.display = '';
    document.getElementById('part-nav').style.display = '';

    speakingSeconds = 0;
    document.getElementById('speaking-timer').textContent = '0:00';
    speakingTimer = setInterval(() => {
      speakingSeconds++;
      const m = Math.floor(speakingSeconds / 60);
      const s = speakingSeconds % 60;
      document.getElementById('speaking-timer').textContent = `${m}:${s.toString().padStart(2, '0')}`;
      if (speakingSeconds >= 10) {
        document.getElementById('speaking-submit').disabled = false;
      }
    }, 1000);

    document.getElementById('status-text').textContent = 'Recording...';
  } catch(e) {
    document.getElementById('speaking-active').style.display = 'none';
    document.getElementById('speaking-error').style.display = 'block';
    document.getElementById('speaking-error').textContent =
      'Microphone access denied. Enable in Chrome Settings → Privacy → Microphone, then reload this page.';
  }
}

function stopRecording() {
  isRecording = false;
  if (recognition) { recognition.stop(); recognition = null; }
  if (mediaRecorder) { mediaRecorder.stop(); mediaRecorder = null; }
  if (speakingTimer) { clearInterval(speakingTimer); speakingTimer = null; }
  document.getElementById('record-btn').classList.remove('recording');
  document.querySelector('.speaking-container')?.classList.remove('recording');
  document.getElementById('status-text').textContent = 'Recording stopped';
  if (speakingSeconds < 10) {
    document.getElementById('speaking-error').style.display = 'block';
    document.getElementById('speaking-error').textContent =
      'Recording too short for evaluation. Please record at least 10 seconds.';
  }
}

async function saveSpeaking() {
  if (isRecording) stopRecording();
  if (!transcript.trim()) {
    document.getElementById('speaking-error').style.display = 'block';
    document.getElementById('speaking-error').textContent = 'No speech detected. Please try again.';
    return;
  }

  // Get task context for the current part
  let taskTitle = '';
  if (speakingTaskData) {
    const test = speakingTaskData.tests.find(t => t.testNumber === currentTestNumber);
    if (test) {
      const part = test.parts.find(p => p.partNumber === currentSpeakingPart);
      if (part) {
        taskTitle = part.partType === 'long-turn' ? (part.cueCard?.topic || '') : (part.topic || '');
      }
    }
  }

  const data = {
    skill: 'speaking',
    source: currentTestSource,
    testNumber: currentTestNumber,
    partNumber: currentSpeakingPart,
    taskTitle: taskTitle,
    transcript: transcript,
    duration: speakingSeconds,
    date: new Date().toISOString(),
    mode: 'practice'
  };

  // Attach audio blob as base64 if available
  if (audioBlob && audioBlob.size > 0) {
    try {
      const base64 = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result.split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(audioBlob);
      });
      data.audioBase64 = base64;
      data.audioMimeType = currentAudioMimeType;
      data.audioSize = audioBlob.size;
    } catch (e) {
      console.warn('Failed to encode audio:', e);
    }
  }

  const result = await saveResult(data);
  if (!result.ok) return;

  document.getElementById('speaking-active').style.display = 'none';
  document.getElementById('speaking-success').style.display = 'block';
  document.getElementById('status-text').textContent = 'Speaking saved';

  // Context-aware success detail
  const detail = document.getElementById('speaking-success-detail');
  const wordCount = transcript.trim().split(/\s+/).length;
  const mins = Math.floor(speakingSeconds / 60);
  const secs = speakingSeconds % 60;
  const durationStr = mins > 0 ? `${mins}:${secs.toString().padStart(2, '0')}` : `${secs}s`;
  detail.innerHTML = `
    ${taskTitle ? '<div style="font-weight:600;margin-bottom:4px">' + taskTitle + '</div>' : ''}
    <div>Duration: ${durationStr} &middot; Words: ~${wordCount}</div>
  `;
}

/* ── Listening ── */
function setupListening() {
  loadListeningTestList();
  document.getElementById('test-select').addEventListener('change', loadTest);
  document.getElementById('listening-submit').addEventListener('click', saveListening);
}

async function loadListeningTestList() {
  const sel = document.getElementById('test-select');
  sel.innerHTML = '<option value="">-- Loading... --</option>';
  try {
    const r = await fetch(BRIDGE_URL + '/api/listening/');
    if (!r.ok) throw new Error('API error');
    const data = await r.json();
    const sources = data.sources || [];
    sel.innerHTML = '<option value="">-- Select a test --</option>';
    if (sources.length === 0) {
      sel.innerHTML = '<option value="">-- No tests available --</option>';
      return;
    }
    // Load first source's tests
    const sourceId = sources[0].id;
    const r2 = await fetch(BRIDGE_URL + '/api/listening/' + sourceId);
    if (!r2.ok) throw new Error('Source not found');
    const testData = await r2.json();
    (testData.tests || []).forEach((t, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = `Cambridge IELTS 1 — Test ${t.testNumber}`;
      opt.dataset.source = sourceId;
      opt.dataset.test = t.testNumber;
      sel.appendChild(opt);
    });
  } catch(e) {
    sel.innerHTML = '<option value="">-- Error loading tests --</option>';
  }
}

async function loadTest() {
  const opt = document.getElementById('test-select').selectedOptions[0];
  if (!opt || !opt.value) return;
  const sourceId = opt.dataset.source;
  const testNum = parseInt(opt.dataset.test);

  document.getElementById('listening-empty').style.display = 'none';
  document.getElementById('listening-active').style.display = '';

  try {
    const r = await fetch(BRIDGE_URL + '/api/listening/' + sourceId);
    if (!r.ok) throw new Error('Source not found');
    const testData = await r.json();
    const test = testData.tests.find(t => t.testNumber === testNum);
    if (!test || !test.sections || !test.sections[0]) return;

    const firstSection = test.sections[0];
    const audio = document.getElementById('audio-player');
    audio.src = BRIDGE_URL + '/audio/' + sourceId + '/' + encodeURIComponent(firstSection.audioFile);

    const panel = document.getElementById('question-panel');
    const questions = firstSection.questions || [];
    panel.innerHTML = `<h3 style="font-family:var(--font-heading);margin-bottom:var(--space-md)">${firstSection.title}</h3>`;
    questions.forEach(q => {
      panel.innerHTML += `
        <div class="question-item">
          <span class="q-num">Q${q.number}</span>
          <input type="text" placeholder="Your answer..." data-q="${q.number}">
        </div>`;
    });
    document.getElementById('status-text').textContent = 'Test loaded — press play';
  } catch(e) {
    document.getElementById('listening-error').style.display = 'block';
    document.getElementById('listening-error').textContent = 'Failed to load test. Is the bridge server running?';
  }
}

async function saveListening() {
  const inputs = document.querySelectorAll('#question-panel input');
  const answers = {};
  inputs.forEach(inp => { answers[inp.dataset.q] = inp.value; });
  const data = {
    skill: 'listening',
    answers: answers,
    test: document.getElementById('test-select').selectedOptions[0]?.textContent || 'Unknown test',
    date: new Date().toISOString()
  };
  const result = await saveResult(data);
  if (!result.ok) return;

  document.getElementById('listening-active').style.display = 'none';
  document.getElementById('listening-success').style.display = 'block';
  document.getElementById('status-text').textContent = 'Answers saved';
}

/* ── Writing ── */
function setupWriting() {
  document.getElementById('essay-input').addEventListener('input', () => {
    document.getElementById('writing-submit').disabled =
      document.getElementById('essay-input').value.trim().length < 50;
  });
  document.getElementById('writing-submit').addEventListener('click', saveWriting);
}

async function saveWriting() {
  const essay = document.getElementById('essay-input').value.trim();
  if (essay.length < 50) return;
  const data = {
    skill: 'writing',
    essay: essay,
    date: new Date().toISOString(),
    taskType: 'Task 2'
  };
  const result = await saveResult(data);
  if (!result.ok) return;

  document.getElementById('status-text').textContent = 'Essay saved — switch to Claude for evaluation';
  document.getElementById('writing-empty').style.display = 'none';
}

/* ── Reading ── */
function setupReading() {
  loadReadingTestList();
  document.getElementById('reading-test-select').addEventListener('change', onReadingTestChange);
  document.getElementById('reading-submit').addEventListener('click', saveReading);
}

async function loadReadingTestList() {
  const sel = document.getElementById('reading-test-select');
  sel.innerHTML = '<option value="">-- Loading... --</option>';
  try {
    const r = await fetch(BRIDGE_URL + '/api/reading/');
    if (!r.ok) throw new Error('API error');
    const data = await r.json();
    const sources = data.sources || [];
    sel.innerHTML = '<option value="">-- Select a test --</option>';
    if (sources.length === 0) {
      sel.innerHTML = '<option value="">-- No tests available --</option>';
      return;
    }
    // Load tests from all sources
    for (const src of sources) {
      const r2 = await fetch(BRIDGE_URL + '/api/reading/' + src.id);
      if (!r2.ok) continue;
      const testData = await r2.json();
      for (const t of (testData.tests || [])) {
        const opt = document.createElement('option');
        opt.value = JSON.stringify({ source: src.id, number: t.testNumber });
        opt.textContent = `Cambridge IELTS ${src.id.replace('cambridge-', '')} — Test ${t.testNumber}`;
        sel.appendChild(opt);
      }
    }
    // Auto-select first test
    if (sel.options.length > 1) {
      sel.selectedIndex = 1;
      onReadingTestChange();
    }
  } catch(e) {
    sel.innerHTML = '<option value="">-- Error loading tests --</option>';
  }
}

function onReadingTestChange() {
  const val = document.getElementById('reading-test-select').value;
  if (!val) return;
  try {
    const t = JSON.parse(val);
    currentTestSource = t.source;
    currentTestNumber = t.number;
    loadReadingTest(t.source, t.number);
  } catch(e) { /* invalid value */ }
}

async function loadReadingTest(source, testNumber) {
  const empty = document.getElementById('reading-empty');
  const active = document.getElementById('reading-active');
  const error = document.getElementById('reading-error');

  empty.style.display = 'none';
  active.style.display = 'none';
  error.style.display = 'none';

  try {
    const url = `${BRIDGE_URL}/textbook/${source}/json/test-${testNumber}-reading.json`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(response.status === 404
        ? 'Test data not found. Run /initialize-json-textbook in Claude first.'
        : `Failed to load test: ${response.status}`);
    }
    currentTestData = await response.json();
    renderReadingTest(currentTestData);
    active.style.display = '';
    document.getElementById('status-text').textContent = `Reading Test ${testNumber} loaded`;
  } catch(e) {
    error.style.display = 'block';
    error.textContent = e.message;
  }
}

function resolveImageUrl(src) {
  return `${BRIDGE_URL}/textbook/${currentTestSource}/textbook/${src}`;
}

function renderReadingTest(data) {
  const passages = data.skills.reading.passages;
  if (!passages || passages.length === 0) return;

  // Render first passage
  const passage = passages[0];
  const passagePanel = document.getElementById('passage-panel');
  passagePanel.innerHTML = `
    <h3>${passage.title}</h3>
    ${passage.images.map(img => renderPassageImage(img)).join('')}
    <div class="passage-text">${escapeHtml(passage.text)}</div>
  `;

  // Render questions
  const questionsPanel = document.getElementById('reading-questions-panel');
  questionsPanel.innerHTML = '';
  passage.questionGroups.forEach(qg => {
    questionsPanel.appendChild(renderQuestionGroup(qg));
  });

  // Restore answers if any
  const storageKey = `reading-test-${currentTestSource}-${currentTestNumber}`;
  const saved = sessionStorage.getItem(storageKey);
  if (saved) {
    const answers = JSON.parse(saved);
    for (const [qNum, val] of Object.entries(answers)) {
      const el = document.querySelector(`[data-reading-q="${qNum}"]`);
      if (el) {
        if (el.type === 'radio') {
          const radio = document.querySelector(`[data-reading-q="${qNum}"][value="${val}"]`);
          if (radio) radio.checked = true;
        } else {
          el.value = val;
        }
      }
    }
  }
}

function renderPassageImage(img) {
  const url = resolveImageUrl(img.src);
  return `<img src="${url}" alt="${escapeHtml(img.alt || '')}" class="passage-image"
    onerror="this.classList.add('missing');this.outerHTML='<div class=\\'passage-image missing\\'>📷 ${escapeHtml(img.alt || 'Image not available')}</div>'">`;
}

function renderQuestionGroup(qg) {
  const div = document.createElement('div');
  div.className = 'question-group';
  div.innerHTML = `
    <h4>${escapeHtml(qg.heading)}</h4>
    <p class="instructions">${escapeHtml(qg.instructions)}</p>
  `;

  // Word list for gap-fill types
  if (qg.wordList && qg.wordList.words && qg.wordList.words.length > 0) {
    const wlDiv = document.createElement('div');
    wlDiv.className = 'word-list';
    wlDiv.innerHTML = `
      <h5>Word List ${qg.wordList.note ? `— ${escapeHtml(qg.wordList.note)}` : ''}</h5>
      <div class="words">${qg.wordList.words.map(w => `<span class="word-chip">${escapeHtml(w)}</span>`).join('')}</div>
    `;
    div.appendChild(wlDiv);
  }

  // Gap text (summary-completion)
  if (qg.gapText) {
    const gapDiv = document.createElement('div');
    gapDiv.className = 'gap-text';
    // Replace (N) with inputs
    const gapHtml = qg.gapText.replace(/\((\d+)\)/g, (match, num) => {
      return ` <input type="text" data-reading-q="${num}" class="q-input" style="width:100px" placeholder="(${num})"> `;
    });
    gapDiv.innerHTML = gapHtml;
    div.appendChild(gapDiv);
  }

  // Table display
  if (qg.table) {
    div.appendChild(renderTableQuestion(qg.table));
  }

  // Form table
  if (qg.formTable) {
    div.appendChild(renderFormTable(qg.formTable));
  }

  // Individual questions
  qg.questions.forEach(q => {
    div.appendChild(renderQuestion(q, qg.questionType));
  });

  return div;
}

function renderTableQuestion(table) {
  const tbl = document.createElement('table');
  tbl.className = 'reading-table';
  if (table.headers) {
    const thead = document.createElement('thead');
    thead.innerHTML = '<tr>' + table.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('') + '</tr>';
    tbl.appendChild(thead);
  }
  if (table.rows) {
    const tbody = document.createElement('tbody');
    table.rows.forEach(row => {
      const tr = document.createElement('tr');
      row.forEach(cell => {
        const td = document.createElement('td');
        td.textContent = cell.value || '';
        if (cell.colspan > 1) td.colSpan = cell.colspan;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    tbl.appendChild(tbody);
  }
  return tbl;
}

function renderFormTable(formTable) {
  const tbl = document.createElement('table');
  tbl.className = 'reading-table';
  if (formTable.headers) {
    const thead = document.createElement('thead');
    thead.innerHTML = '<tr>' + formTable.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('') + '</tr>';
    tbl.appendChild(thead);
  }
  if (formTable.rows) {
    const tbody = document.createElement('tbody');
    formTable.rows.forEach(row => {
      const tr = document.createElement('tr');
      row.forEach(cell => {
        const td = document.createElement('td');
        if (cell.colspan > 1) td.colSpan = cell.colspan;
        if (cell.hasInput) {
          const inputNums = Array.isArray(cell.inputFor) ? cell.inputFor : [cell.inputFor];
          inputNums.forEach(num => {
            const inp = document.createElement('input');
            inp.type = 'text';
            inp.dataset.readingQ = String(num);
            inp.className = 'q-input';
            inp.style.width = inputNums.length > 1 ? '80px' : '150px';
            inp.placeholder = `(${num})`;
            td.appendChild(inp);
            if (inputNums.length > 1 && num !== inputNums[inputNums.length - 1]) {
              td.appendChild(document.createTextNode(' '));
            }
          });
        } else {
          td.innerHTML = escapeHtml(cell.value || '').replace(/\n/g, '<br>');
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    tbl.appendChild(tbody);
  }
  return tbl;
}

function renderQuestion(q, groupType) {
  const div = document.createElement('div');
  div.className = 'reading-question';

  const qType = q.type || groupType;

  // Question images
  let imageHtml = '';
  if (q.images && q.images.length > 0) {
    imageHtml = q.images.map(img => {
      const url = resolveImageUrl(img.src);
      return `<img src="${url}" alt="${escapeHtml(img.alt || '')}" class="q-image"
        onerror="this.classList.add('missing');this.outerHTML='<div class=\\'q-image missing\\'>📷 ${escapeHtml(img.alt || 'Image not available')}</div>'">`;
    }).join('');
  }

  switch (qType) {
  case 'multiple-choice':
  case 'multiple-choice-image':
    div.innerHTML = `
      <div class="q-text">${q.number}. ${escapeHtml(q.text)}</div>
      ${imageHtml}
      <div class="q-options">
        ${(q.options || []).map(o => `
          <label>
            <input type="radio" name="reading-q-${q.number}" data-reading-q="${q.number}" value="${escapeHtml(o.label)}">
            <span><strong>${escapeHtml(o.label)}</strong> ${escapeHtml(o.text)}</span>
          </label>
        `).join('')}
      </div>`;
    break;

  case 'true-false-not-given':
    div.innerHTML = `
      <div class="q-text">${q.number}. ${escapeHtml(q.text)}</div>
      <div class="q-options">
        <label><input type="radio" name="reading-q-${q.number}" data-reading-q="${q.number}" value="TRUE"> TRUE</label>
        <label><input type="radio" name="reading-q-${q.number}" data-reading-q="${q.number}" value="FALSE"> FALSE</label>
        <label><input type="radio" name="reading-q-${q.number}" data-reading-q="${q.number}" value="NOT GIVEN"> NOT GIVEN</label>
      </div>`;
    break;

  case 'yes-no-not-given':
    div.innerHTML = `
      <div class="q-text">${q.number}. ${escapeHtml(q.text)}</div>
      <div class="q-options">
        <label><input type="radio" name="reading-q-${q.number}" data-reading-q="${q.number}" value="YES"> YES</label>
        <label><input type="radio" name="reading-q-${q.number}" data-reading-q="${q.number}" value="NO"> NO</label>
        <label><input type="radio" name="reading-q-${q.number}" data-reading-q="${q.number}" value="NOT GIVEN"> NOT GIVEN</label>
      </div>`;
    break;

  case 'matching':
    div.innerHTML = `
      <div class="q-text">${q.number}. ${escapeHtml(q.text)}</div>
      <div class="q-options">
        ${(q.options || []).map(o => `
          <label>
            <input type="radio" name="reading-q-${q.number}" data-reading-q="${q.number}" value="${escapeHtml(o.label)}">
            <span><strong>${escapeHtml(o.label)}</strong> — ${escapeHtml(o.text)}</span>
          </label>
        `).join('')}
      </div>`;
    break;

  case 'short-answer':
  default:
    div.innerHTML = `
      <div class="q-text">${q.number}. ${escapeHtml(q.text)}</div>
      ${imageHtml}
      <input type="text" data-reading-q="${q.number}" class="q-input" placeholder="Your answer...">`;
    break;
  }

  return div;
}

async function saveReading() {
  const inputs = document.querySelectorAll('[data-reading-q]');
  const answers = {};

  inputs.forEach(inp => {
    const qNum = inp.dataset.readingQ;
    if (inp.type === 'radio') {
      if (inp.checked) answers[qNum] = inp.value;
    } else {
      if (inp.value.trim()) answers[qNum] = inp.value.trim();
    }
  });

  // Save to sessionStorage
  const storageKey = `reading-test-${currentTestSource}-${currentTestNumber}`;
  sessionStorage.setItem(storageKey, JSON.stringify(answers));

  const data = {
    skill: 'reading',
    testSource: currentTestSource,
    testNumber: currentTestNumber,
    answers: answers,
    date: new Date().toISOString()
  };

  const result = await saveResult(data);
  if (!result.ok) return;

  document.getElementById('reading-active').style.display = 'none';
  document.getElementById('reading-success').style.display = 'block';
  document.getElementById('status-text').textContent = 'Reading answers saved';
}

/* ── Utility ── */
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/* ── Keyboard Nav ── */
function setupKeyboardNav() {
  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && currentMode === 'speaking' && e.target === document.body) {
      e.preventDefault();
      document.getElementById('record-btn').click();
    }
  });
}

/* ── Poll for roadmap updates ── */
setInterval(async () => {
  try {
    const r = await fetch(BRIDGE_URL + '/roadmap.json');
    if (r.ok) {
      const data = await r.json();
      if (JSON.stringify(data) !== JSON.stringify(roadmap)) {
        roadmap = data;
        renderRoadmap();
      }
    }
  } catch(e) { /* roadmap not available yet */ }
}, 5000);

/* ── Onboarding ── */
window.addEventListener('load', () => {
  const shown = sessionStorage.getItem('ielts-studio-onboarding-shown');
  if (!shown) {
    sessionStorage.setItem('ielts-studio-onboarding-shown', '1');
    setTimeout(() => {
      document.getElementById('status-text').textContent =
        'Welcome! Record speaking, take a listening or reading test, or write an essay. Then switch to Claude for evaluation.';
    }, 500);
  }
});
