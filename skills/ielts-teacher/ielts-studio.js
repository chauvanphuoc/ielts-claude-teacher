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
let roadmap = null;
let currentTestData = null;  // loaded JSON test data
let currentTestSource = 'cambridge-1';
let currentTestNumber = 1;

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
    const chunks = [];
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    mediaRecorder.onstop = () => { stream.getTracks().forEach(t => t.stop()); };
    mediaRecorder.start();

    isRecording = true;
    document.getElementById('record-btn').classList.add('recording');
    document.querySelector('.speaking-container')?.classList.add('recording');
    document.getElementById('speaking-empty').style.display = 'none';
    document.getElementById('speaking-active').style.display = '';
    document.getElementById('speaking-success').style.display = 'none';
    document.getElementById('speaking-submit').disabled = true;

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
  const data = {
    skill: 'speaking',
    transcript: transcript,
    duration: speakingSeconds,
    date: new Date().toISOString(),
    mode: 'practice'
  };
  try {
    const r = await fetch(BRIDGE_URL + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (r.ok) {
      document.getElementById('speaking-active').style.display = 'none';
      document.getElementById('speaking-success').style.display = 'block';
      document.getElementById('status-text').textContent = 'Speaking saved';
    } else {
      throw new Error('Save failed: ' + r.status);
    }
  } catch(e) {
    document.getElementById('speaking-error').style.display = 'block';
    document.getElementById('speaking-error').textContent =
      'Failed to save. Is the bridge server running? Check Claude and say "/ielts-check".';
  }
}

/* ── Listening ── */
function setupListening() {
  loadTestList();
  document.getElementById('test-select').addEventListener('change', loadTest);
  document.getElementById('listening-submit').addEventListener('click', saveListening);
}

function loadTestList() {
  const sel = document.getElementById('test-select');
  const tests = [
    { name: 'Cambridge IELTS 1 — Test 1', sections: ['Test 1 - Section 1.mp3','Test 1 - Section 2.mp3','Test 1 - Section 3.mp3','Test 1 - Section 4.mp3'] },
    { name: 'Cambridge IELTS 1 — Test 2', sections: ['Test 2 - Section 1.mp3','Test 2 - Section 2.mp3','Test 2 - Section 3.mp3','Test 2 - Section 4.mp3'] },
    { name: 'Cambridge IELTS 1 — Test 3', sections: ['Test 3 - Section 1.mp3','Test 3 - Section 2.mp3','Test 3 - Section 3.mp3','Test 3 - Section 4.mp3'] },
    { name: 'Cambridge IELTS 1 — Test 4', sections: ['Test 4 - Section 1.mp3','Test 4 - Section 2.mp3','Test 4 - Section 3.mp3','Test 4 - Section 4.mp3'] }
  ];
  tests.forEach((t, i) => {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = t.name;
    sel.appendChild(opt);
  });
}

function loadTest() {
  const idx = document.getElementById('test-select').value;
  if (idx === '') return;
  document.getElementById('listening-empty').style.display = 'none';
  document.getElementById('listening-active').style.display = '';
  const tests = [
    ['Test 1 - Section 1.mp3','Test 1 - Section 2.mp3','Test 1 - Section 3.mp3','Test 1 - Section 4.mp3'],
    ['Test 2 - Section 1.mp3','Test 2 - Section 2.mp3','Test 2 - Section 3.mp3','Test 2 - Section 4.mp3'],
    ['Test 3 - Section 1.mp3','Test 3 - Section 2.mp3','Test 3 - Section 3.mp3','Test 3 - Section 4.mp3'],
    ['Test 4 - Section 1.mp3','Test 4 - Section 2.mp3','Test 4 - Section 3.mp3','Test 4 - Section 4.mp3']
  ];
  const sections = tests[parseInt(idx)];
  const audio = document.getElementById('audio-player');
  audio.src = BRIDGE_URL + '/audio/cambridge-1/' + encodeURIComponent(sections[0]);
  const panel = document.getElementById('question-panel');
  panel.innerHTML = '<h3 style="font-family:var(--font-heading);margin-bottom:var(--space-md)">Section 1 — Questions 1-10</h3>';
  for (let i = 1; i <= 10; i++) {
    panel.innerHTML += `
      <div class="question-item">
        <span class="q-num">Q${i}</span>
        <input type="text" placeholder="Your answer..." data-q="${i}">
      </div>`;
  }
  document.getElementById('status-text').textContent = 'Test loaded — press play';
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
  try {
    const r = await fetch(BRIDGE_URL + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (r.ok) {
      document.getElementById('listening-active').style.display = 'none';
      document.getElementById('listening-success').style.display = 'block';
      document.getElementById('status-text').textContent = 'Answers saved';
    } else {
      throw new Error('Save failed');
    }
  } catch(e) {
    document.getElementById('listening-error').style.display = 'block';
    document.getElementById('listening-error').textContent = 'Failed to save. Is the bridge running?';
  }
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
  try {
    const r = await fetch(BRIDGE_URL + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (r.ok) {
      document.getElementById('status-text').textContent = 'Essay saved — switch to Claude for evaluation';
      document.getElementById('writing-empty').style.display = 'none';
    } else {
      throw new Error('Save failed');
    }
  } catch(e) {
    document.getElementById('writing-error').style.display = 'block';
    document.getElementById('writing-error').textContent = 'Failed to save. Is the bridge running?';
  }
}

/* ── Reading ── */
function setupReading() {
  loadReadingTestList();
  document.getElementById('reading-test-select').addEventListener('change', onReadingTestChange);
  document.getElementById('reading-submit').addEventListener('click', saveReading);
}

function loadReadingTestList() {
  const sel = document.getElementById('reading-test-select');
  sel.innerHTML = '<option value="">-- Select a test --</option>';
  const tests = [
    { name: 'Cambridge IELTS 1 — Test 1', source: 'cambridge-1', number: 1 },
    { name: 'Cambridge IELTS 1 — Test 2', source: 'cambridge-1', number: 2 },
    { name: 'Cambridge IELTS 1 — Test 3', source: 'cambridge-1', number: 3 },
    { name: 'Cambridge IELTS 1 — Test 4', source: 'cambridge-1', number: 4 }
  ];
  tests.forEach((t, i) => {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = t.name;
    sel.appendChild(opt);
  });
}

async function onReadingTestChange() {
  const idx = document.getElementById('reading-test-select').value;
  if (idx === '') return;

  const tests = [
    { source: 'cambridge-1', number: 1 },
    { source: 'cambridge-1', number: 2 },
    { source: 'cambridge-1', number: 3 },
    { source: 'cambridge-1', number: 4 }
  ];
  const t = tests[parseInt(idx)];
  currentTestSource = t.source;
  currentTestNumber = t.number;

  await loadReadingTest(t.source, t.number);
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

  try {
    const r = await fetch(BRIDGE_URL + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (r.ok) {
      document.getElementById('reading-active').style.display = 'none';
      document.getElementById('reading-success').style.display = 'block';
      document.getElementById('status-text').textContent = 'Reading answers saved';
    } else {
      throw new Error('Save failed');
    }
  } catch(e) {
    document.getElementById('reading-error').style.display = 'block';
    document.getElementById('reading-error').textContent = 'Failed to save. Is the bridge running?';
  }
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
