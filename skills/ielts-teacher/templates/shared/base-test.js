/* ============================================================
   base-test.js — Shared app logic for all IELTS templates.
   Used by: mini-test.html, listening-test.html, diagnostic-test.html

   Expects: window.__TEST_CONFIG__ from the template.
   ============================================================ */

(function() {
  'use strict';

  // ── Configuration — re-read from window.__TEST_CONFIG__ on each access
  //    because listening templates set it asynchronously after script load.
  function getConfig() { return window.__TEST_CONFIG__ || {}; }
  function getQuestions() { return getConfig().questions || []; }
  function getKcTags() { return getConfig().kcTags || []; }
  function getSkill() { return getConfig().skill || 'reading'; }
  function getTestTitle() { return getConfig().testTitle || document.title; }
  function getBridgeUrl() { return getConfig().bridgeUrl || 'http://localhost:8765'; }
  function getSections() { return getConfig().sections || null; }
  var currentSection = 0;
  function getTotalSections() { var s = getSections(); return s ? s.length : 1; }

  var container = document.getElementById('questions-container');
  var form = document.getElementById('test-form');
  var resultsDiv = document.getElementById('results');
  var warningBanner = document.getElementById('warning-banner');
  var validationWarning = document.getElementById('validation-warning');
  var unansweredCount = document.getElementById('unanswered-count');
  var submitHint = document.getElementById('submit-hint');

  // ============================================================
  // RENDER QUESTIONS BY TYPE
  // ============================================================

  function getQuestionsForSection() {
    var s = getSections();
    if (!s) return getQuestions();
    return s[currentSection].questions || [];
  }

  function renderQuestions() {
    if (!container) return;
    container.innerHTML = '';

    var qs = getQuestionsForSection();
    qs.forEach(function(q) {
      var div = document.createElement('div');
      div.className = 'question';
      div.id = 'question-' + q.number;

      var num = document.createElement('div');
      num.className = 'question-number';
      num.textContent = 'Question ' + q.number;
      div.appendChild(num);

      var text = document.createElement('div');
      text.className = 'question-text';
      text.textContent = q.text;
      div.appendChild(text);

      switch (q.type) {
        case 'true-false-not-given':
        case 'yes-no-not-given':
          renderTFNG(div, q);
          break;
        case 'multiple-choice':
          renderMC(div, q);
          break;
        case 'multiple-choice-image':
          renderMCImage(div, q);
          break;
        case 'gap-fill':
        case 'short-answer':
          renderGapFill(div, q);
          break;
        case 'matching':
          renderMatching(div, q);
          break;
        case 'matching-checkboxes':
          renderMatchingCheckboxes(div, q);
          break;
        case 'form-completion':
          renderFormCompletion(div, q);
          break;
        default:
          console.warn('Unknown question type:', q.type);
      }

      container.appendChild(div);
    });

    if (submitHint) {
      submitHint.textContent = qs.length + ' questions';
    }
  }

  function renderTFNG(container, q) {
    var row = document.createElement('div');
    row.className = 'options-row';
    row.setAttribute('role', 'radiogroup');
    row.setAttribute('aria-label', 'Question ' + q.number + ' answer options');

    var labels = q.type === 'yes-no-not-given'
      ? ['YES', 'NO', 'NOT GIVEN']
      : ['TRUE', 'FALSE', 'NOT GIVEN'];

    labels.forEach(function(value, idx) {
      var opt = document.createElement('div');
      opt.className = 'option';

      var input = document.createElement('input');
      input.type = 'radio';
      input.name = 'q' + q.number;
      input.id = 'q' + q.number + '-' + idx;
      input.value = value;
      input.setAttribute('data-question', q.number);

      var label = document.createElement('label');
      label.setAttribute('for', 'q' + q.number + '-' + idx);
      label.textContent = value;
      label.className = value === 'TRUE' || value === 'YES' ? 'label-true'
        : value === 'FALSE' || value === 'NO' ? 'label-false'
        : 'label-not-given';

      opt.appendChild(input);
      opt.appendChild(label);
      row.appendChild(opt);
    });

    container.appendChild(row);
  }

  function renderMC(container, q) {
    var row = document.createElement('div');
    row.className = 'options-vertical';
    row.setAttribute('role', 'radiogroup');
    row.setAttribute('aria-label', 'Question ' + q.number + ' answer options');

    (q.options || []).forEach(function(opt, idx) {
      var div = document.createElement('div');
      div.className = 'option-mc';

      var input = document.createElement('input');
      input.type = 'radio';
      input.name = 'q' + q.number;
      input.id = 'q' + q.number + '-' + idx;
      input.value = opt.label;
      input.setAttribute('data-question', q.number);

      var label = document.createElement('label');
      label.setAttribute('for', 'q' + q.number + '-' + idx);
      label.innerHTML = '<span class="option-label-marker">' + escapeHtml(opt.label) + '</span> ' + escapeHtml(opt.text);

      div.appendChild(input);
      div.appendChild(label);
      row.appendChild(div);
    });

    container.appendChild(row);
  }

  function renderMCImage(container, q) {
    // Check if individual option images exist (future textbooks may have them)
    var hasIndividualImages = (q.options || []).some(function(opt) { return opt.image; });

    if (hasIndividualImages) {
      // Image grid mode: each option has its own image
      var grid = document.createElement('div');
      grid.className = 'options-image-grid';
      grid.setAttribute('role', 'radiogroup');
      grid.setAttribute('aria-label', 'Question ' + q.number + ' answer options');

      (q.options || []).forEach(function(opt, idx) {
        var div = document.createElement('div');
        div.className = 'option-img';

        var input = document.createElement('input');
        input.type = 'radio';
        input.name = 'q' + q.number;
        input.id = 'q' + q.number + '-img-' + idx;
        input.value = opt.label;
        input.setAttribute('data-question', q.number);

        var label = document.createElement('label');
        label.setAttribute('for', 'q' + q.number + '-img-' + idx);

        var img = document.createElement('img');
        img.src = opt.image || '';
        img.alt = 'Option ' + opt.label;
        img.setAttribute('loading', 'lazy');
        img.onerror = function() {
          this.style.display = 'none';
          var fallback = document.createElement('div');
          fallback.style.cssText = 'padding:40px 20px;text-align:center;font-size:13px;color:#9ca3af;';
          fallback.textContent = 'Image not available';
          this.parentNode.insertBefore(fallback, this.nextSibling);
        };

        var imgLabel = document.createElement('div');
        imgLabel.className = 'img-label';
        imgLabel.textContent = opt.label;

        label.appendChild(img);
        label.appendChild(imgLabel);
        div.appendChild(input);
        div.appendChild(label);
        grid.appendChild(div);
      });

      container.appendChild(grid);
    } else {
      // Single-image mode: show the question image, then text radio buttons below
      if (q.image) {
        var imgDiv = document.createElement('div');
        imgDiv.className = 'question-image';
        var img = document.createElement('img');
        img.src = '/textbook/' + (window.__TEST_CONFIG__ && window.__TEST_CONFIG__.sourceId || 'cambridge-1') + '/textbook/' + q.image;
        img.alt = 'Question ' + q.number + ' image';
        img.setAttribute('loading', 'lazy');
        img.onerror = function() {
          this.style.display = 'none';
          var fb = document.createElement('div');
          fb.className = 'question-image-fallback';
          fb.textContent = 'Image not available — refer to textbook page';
          this.parentNode.appendChild(fb);
        };
        imgDiv.appendChild(img);
        container.appendChild(imgDiv);
      }

      // Text radio buttons below the image
      var row = document.createElement('div');
      row.className = 'options-vertical';
      row.setAttribute('role', 'radiogroup');
      row.setAttribute('aria-label', 'Question ' + q.number + ' answer options');

      (q.options || []).forEach(function(opt, idx) {
        var div = document.createElement('div');
        div.className = 'option-mc';

        var input = document.createElement('input');
        input.type = 'radio';
        input.name = 'q' + q.number;
        input.id = 'q' + q.number + '-' + idx;
        input.value = opt.label;
        input.setAttribute('data-question', q.number);

        var label = document.createElement('label');
        label.setAttribute('for', 'q' + q.number + '-' + idx);
        var labelText = opt.label;
        if (opt.text) labelText += ' ' + opt.text;
        label.innerHTML = '<span class="option-label-marker">' + escapeHtml(opt.label) + '</span>' + (opt.text ? ' ' + escapeHtml(opt.text) : '');

        div.appendChild(input);
        div.appendChild(label);
        row.appendChild(div);
      });

      container.appendChild(row);
    }
  }

  function renderGapFill(container, q) {
    var text = q.text || '';
    var inputHtml = '<input type="text" class="gap-input" name="q' + q.number +
      '" data-question="' + q.number + '" aria-label="Answer for question ' + q.number + '" autocomplete="off" spellcheck="false">';
    var displayText = text.replace(/_{3,}/g, inputHtml);

    var div = document.createElement('div');
    div.className = 'gap-fill-text';
    div.innerHTML = displayText;
    container.appendChild(div);
  }

  function renderMatching(container, q) {
    var table = document.createElement('table');
    table.className = 'matching-table';
    table.setAttribute('role', 'group');
    table.setAttribute('aria-label', 'Question ' + q.number + ' — match each item');

    var thead = document.createElement('thead');
    thead.innerHTML = '<tr><th>Item</th><th>Match to</th></tr>';
    table.appendChild(thead);

    var tbody = document.createElement('tbody');
    (q.items || []).forEach(function(item) {
      var tr = document.createElement('tr');

      var tdLabel = document.createElement('td');
      tdLabel.textContent = item.label + '. ' + item.text;
      tr.appendChild(tdLabel);

      var tdSelect = document.createElement('td');
      var select = document.createElement('select');
      select.className = 'matching-select';
      select.name = 'q' + q.number + '-' + item.label;
      select.setAttribute('data-question', q.number);
      select.setAttribute('data-item', item.label);
      select.setAttribute('aria-label', 'Match ' + item.label + ' to');

      var defaultOpt = document.createElement('option');
      defaultOpt.value = '';
      defaultOpt.textContent = '-- Select --';
      select.appendChild(defaultOpt);

      (q.options || []).forEach(function(opt) {
        var option = document.createElement('option');
        option.value = opt.label;
        option.textContent = opt.label + '. ' + opt.text;
        select.appendChild(option);
      });

      tdSelect.appendChild(select);
      tr.appendChild(tdSelect);
      tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    container.appendChild(table);
  }

  function renderMatchingCheckboxes(container, q) {
    if (q.selectCount) {
      var hint = document.createElement('div');
      hint.className = 'checkbox-count-hint';
      hint.textContent = 'Select ' + q.selectCount + ' answer(s)';
      container.appendChild(hint);
    }

    var row = document.createElement('div');
    row.className = 'options-checkboxes';
    row.setAttribute('role', 'group');
    row.setAttribute('aria-label', 'Question ' + q.number + ' answer options');

    (q.items || q.options || []).forEach(function(item, idx) {
      var div = document.createElement('div');
      div.className = 'option-cb';

      var input = document.createElement('input');
      input.type = 'checkbox';
      input.name = 'q' + q.number + '-' + idx;
      input.id = 'q' + q.number + '-' + idx;
      input.value = item.label;
      input.setAttribute('data-question', q.number);

      if (q.selectCount) {
        input.addEventListener('change', function() {
          var checked = container.querySelectorAll('input[data-question="' + q.number + '"]:checked');
          if (checked.length > q.selectCount) {
            input.checked = false;
          }
        });
      }

      var label = document.createElement('label');
      label.setAttribute('for', 'q' + q.number + '-' + idx);
      label.innerHTML = '<span class="option-label-marker">' + escapeHtml(item.label) + '</span> ' + escapeHtml(item.text || '');

      div.appendChild(input);
      div.appendChild(label);
      row.appendChild(div);
    });

    container.appendChild(row);
  }

  function renderFormCompletion(container, q) {
    var table = document.createElement('table');
    table.className = 'form-table';
    table.setAttribute('role', 'group');
    table.setAttribute('aria-label', 'Question ' + q.number);

    if (q.headers) {
      var thead = document.createElement('thead');
      thead.innerHTML = '<tr>' + q.headers.map(function(h) { return '<th>' + escapeHtml(h) + '</th>'; }).join('') + '</tr>';
      table.appendChild(thead);
    }

    var tbody = document.createElement('tbody');
    (q.rows || []).forEach(function(row) {
      var tr = document.createElement('tr');
      row.forEach(function(cell) {
        var td = document.createElement('td');
        if (cell.input) {
          // Support prefix text before input (e.g., "£___" or "___ Road")
          if (cell.prefix) {
            var prefixSpan = document.createElement('span');
            prefixSpan.textContent = cell.prefix;
            prefixSpan.style.cssText = 'margin-right:4px;';
            td.appendChild(prefixSpan);
          }
          var input = document.createElement('input');
          input.type = 'text';
          input.className = 'form-input';
          input.name = 'q' + q.number + '-' + cell.key;
          input.setAttribute('data-question', q.number);
          input.setAttribute('data-key', cell.key);
          input.setAttribute('aria-label', cell.label || cell.key);
          input.setAttribute('autocomplete', 'off');
          input.setAttribute('spellcheck', 'false');
          td.appendChild(input);
          // Support suffix text after input (e.g., "Road" after address number)
          if (cell.suffix) {
            var suffixSpan = document.createElement('span');
            suffixSpan.textContent = ' ' + cell.suffix;
            suffixSpan.style.cssText = 'margin-left:4px;';
            td.appendChild(suffixSpan);
          }
        } else {
          td.textContent = cell.text || '';
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    container.appendChild(table);
  }

  // ============================================================
  // COLLECT ANSWERS
  // ============================================================

  function collectAnswers() {
    var answers = {};
    var unanswered = [];
    var qs = getQuestionsForSection();

    qs.forEach(function(q) {
      var key = String(q.number);

      switch (q.type) {
        case 'true-false-not-given':
        case 'yes-no-not-given':
        case 'multiple-choice':
        case 'multiple-choice-image': {
          var selected = document.querySelector('input[name="q' + q.number + '"]:checked');
          if (selected) {
            answers[key] = selected.value;
          } else {
            unanswered.push(q.number);
          }
          break;
        }
        case 'gap-fill':
        case 'short-answer': {
          var input = document.querySelector('input[name="q' + q.number + '"]');
          if (input && input.value.trim()) {
            answers[key] = input.value.trim();
          } else {
            unanswered.push(q.number);
          }
          break;
        }
        case 'matching': {
          var allAnswered = true;
          (q.items || []).forEach(function(item) {
            var select = document.querySelector('select[name="q' + q.number + '-' + item.label + '"]');
            if (select && select.value) {
              answers[key + '-' + item.label] = select.value;
            } else {
              allAnswered = false;
            }
          });
          if (!allAnswered) unanswered.push(q.number);
          break;
        }
        case 'matching-checkboxes': {
          var checked = document.querySelectorAll('input[data-question="' + q.number + '"]:checked');
          if (checked.length > 0) {
            var values = [];
            checked.forEach(function(cb) { values.push(cb.value); });
            answers[key] = values;
          } else {
            unanswered.push(q.number);
          }
          break;
        }
        case 'form-completion': {
          var allAnswered = true;
          (q.rows || []).forEach(function(row) {
            row.forEach(function(cell) {
              if (cell.input) {
                var input = document.querySelector('input[name="q' + q.number + '-' + cell.key + '"]');
                if (input && input.value.trim()) {
                  answers[cell.key] = input.value.trim();
                } else {
                  allAnswered = false;
                }
              }
            });
          });
          if (!allAnswered) unanswered.push(q.number);
          break;
        }
      }
    });

    return { answers: answers, unanswered: unanswered };
  }

  // ============================================================
  // SCORE + SHOW RESULTS
  // ============================================================

  function isTextInputType(qType) {
    return qType === 'gap-fill' || qType === 'gapfill' || qType === 'short-answer' ||
           qType === 'form-completion' || qType === 'table-completion' ||
           qType === 'note-completion' || qType === 'sentence-completion' ||
           qType === 'diagram-labeling' || qType === 'summary-completion' ||
           qType === 'matching';
  }

  function checkTextAnswersWithLLM(textResults) {
    if (!textResults.length) return Promise.resolve([]);
    var payload = {
      answers: textResults.map(function(r) {
        return {
          questionNumber: r.number,
          userAnswer: r.userAnswer,
          correctAnswer: r.correctAnswer,
          questionText: r.questionText || '',
          instructions: r.instructions || ''
        };
      })
    };
    return fetch(getBridgeUrl() + '/check-text-answers', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    }).then(function(resp) {
      if (!resp.ok) throw new Error('Server returned ' + resp.status);
      return resp.json();
    }).then(function(data) {
      if (data && data.results) return data.results;
      return [];
    }).catch(function(err) {
      console.warn('LLM check failed:', err);
      return [];  // fallback: keep original results
    });
  }

  function scoreAnswers(userAnswers) {
    var qs = getQuestionsForSection();
    var total = qs.length;
    var correct = 0;
    var results = [];
    var textMismatches = [];  // text answers that failed local check → send to LLM

    qs.forEach(function(q) {
      var userAnswer, isCorrect;

      switch (q.type) {
        case 'true-false-not-given':
        case 'yes-no-not-given':
        case 'multiple-choice':
        case 'multiple-choice-image':
          userAnswer = userAnswers[String(q.number)] || '(no answer)';
          isCorrect = userAnswer === q.correctAnswer;
          break;

        case 'gap-fill':
        case 'short-answer':
          userAnswer = userAnswers[String(q.number)] || '(no answer)';
          var acceptable = q.acceptableAnswers || [q.correctAnswer];
          isCorrect = acceptable.some(function(a) {
            return a.toLowerCase().trim() === userAnswer.toLowerCase().trim();
          });
          // NOTE: gap-fill/short-answer = exact match only (IELTS spelling).
          // No LLM semantic check — synonyms are NOT acceptable.
          break;

        case 'matching':
          var itemCorrect = true;
          (q.items || []).forEach(function(item) {
            var matchKey = q.number + '-' + item.label;
            var matchAnswer = userAnswers[matchKey] || '';
            if (matchAnswer !== (q.correctMatches || {})[item.label]) {
              itemCorrect = false;
            }
          });
          userAnswer = JSON.stringify(userAnswers);
          isCorrect = itemCorrect;
          break;

        case 'matching-checkboxes':
          var userVals = userAnswers[String(q.number)] || [];
          var correctVals = q.correctAnswers || [];
          userAnswer = userVals.join(', ') || '(no answer)';
          isCorrect = arraysEqual(userVals.sort(), correctVals.sort());
          break;

        case 'form-completion':
          var formCorrect = true;
          (q.rows || []).forEach(function(row) {
            row.forEach(function(cell) {
              if (cell.input) {
                var cellAnswer = userAnswers[cell.key] || '';
                var cellAcceptable = cell.acceptableAnswers || [cell.correctAnswer];
                var cellIsCorrect = cellAcceptable.some(function(a) {
                  return a.toLowerCase().trim() === cellAnswer.toLowerCase().trim();
                });
                if (!cellIsCorrect) formCorrect = false;
              }
            });
          });
          userAnswer = JSON.stringify(userAnswers);
          isCorrect = formCorrect;
          // Collect for LLM check if local check failed
          if (!isCorrect && q.correctAnswer) {
            textMismatches.push({
              number: q.number,
              userAnswer: JSON.stringify(userAnswers),
              correctAnswer: typeof q.correctAnswer === 'string' ? q.correctAnswer : JSON.stringify(q.correctAnswer),
              questionText: q.text || '',
              instructions: q.instructions || ''
            });
          }
          break;

        default:
          isCorrect = false;
          userAnswer = '(unknown type)';
      }

      if (isCorrect) correct++;
      results.push({
        number: q.number,
        correct: isCorrect,
        userAnswer: userAnswer,
        correctAnswer: q.correctAnswer || (q.correctAnswers || []).join(', '),
        explanation: q.explanation || ''
      });
    });

    var scoring = { total: total, correct: correct, results: results };

    // If there are text mismatches, check them with LLM
    if (textMismatches.length > 0) {
      return checkTextAnswersWithLLM(textMismatches).then(function(llmResults) {
        var llmMap = {};
        llmResults.forEach(function(r) { llmMap[r.questionNumber] = r.correct; });
        scoring.results.forEach(function(r) {
          if (llmMap[r.number] === true) {
            r.correct = true;
            scoring.correct++;
          }
        });
        return scoring;
      });
    }

    return Promise.resolve(scoring);
  }

  function showResults(scoring) {
    if (!resultsDiv) return;

    var pct = scoring.total > 0 ? Math.round((scoring.correct / scoring.total) * 100) : 0;
    var isGood = pct >= 60;

    var headerClass = isGood ? 'great-job' : 'needs-work';
    var emoji = isGood ? '&#127775;' : '&#128170;';
    var title = isGood ? 'Great work!' : 'Keep going!';
    var message = isGood
      ? 'You\'re making solid progress. Ready for the next challenge?'
      : 'These are opportunities to improve. Each mistake is a chance to learn something new. Let\'s look at what needs work.';

    var html = '';
    html += '<div class="results-header ' + headerClass + '">';
    html += '  <div class="results-score">' + emoji + ' ' + scoring.correct + '/' + scoring.total + '</div>';
    html += '  <div class="results-label">' + title + '</div>';
    html += '  <div class="results-message">' + message + '</div>';
    html += '</div>';

    scoring.results.forEach(function(r) {
      var cls = r.correct ? 'correct' : 'incorrect';
      var icon = r.correct ? '&#10003;' : '&#10007;';
      html += '<div class="result-item ' + cls + '">';
      html += '  <span class="result-icon">' + icon + '</span>';
      html += '  <span>';
      html += '    <strong>Q' + r.number + ' — ' + (r.correct ? 'Correct' : 'Incorrect') + '</strong>';
      if (!r.correct) {
        html += '<br>Your answer: <em>' + escapeHtml(String(r.userAnswer)) + '</em>';
        html += ' &rarr; Correct: <em>' + escapeHtml(String(r.correctAnswer)) + '</em>';
      }
      if (r.explanation) {
        html += '<br>' + escapeHtml(r.explanation);
      }
      html += '  </span>';
      html += '</div>';
    });

    resultsDiv.innerHTML = html;
    resultsDiv.classList.add('visible');
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ============================================================
  // TRANSCRIPT TOGGLE (listening)
  // ============================================================

  window.toggleTranscript = function() {
    var panel = document.getElementById('transcript-panel');
    if (panel) {
      panel.classList.toggle('open');
    }
  };

  // ============================================================
  // SAVE RESULTS (POST /save with localStorage fallback)
  // ============================================================

  function saveResults(scoring) {
    var payload = {
      skill: getSkill(),
      kcTags: getKcTags(),
      testTitle: getTestTitle(),
      date: new Date().toISOString(),
      totalQuestions: scoring.total,
      correctCount: scoring.correct,
      score: scoring.total > 0 ? Math.round((scoring.correct / scoring.total) * 100) : 0,
      results: scoring.results
    };

    fetch(getBridgeUrl() + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(function(resp) {
      if (!resp.ok) throw new Error('Server returned ' + resp.status);
      return resp.json();
    })
    .then(function(data) {
      console.log('Results saved:', data);
      clearPendingResults();
    })
    .catch(function(err) {
      console.warn('Save failed, storing in localStorage:', err.message);
      localStorage.setItem('pendingResults_' + getSkill(), JSON.stringify(payload));
      if (warningBanner) warningBanner.classList.add('visible');
    });
  }

  window.retrySave = function() {
    var pending = localStorage.getItem('pendingResults_' + getSkill());
    if (!pending) {
      if (warningBanner) warningBanner.classList.remove('visible');
      return;
    }

    fetch(getBridgeUrl() + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: pending
    })
    .then(function(resp) {
      if (!resp.ok) throw new Error('Server returned ' + resp.status);
      return resp.json();
    })
    .then(function() {
      clearPendingResults();
      if (warningBanner) warningBanner.classList.remove('visible');
      console.log('Pending results saved successfully.');
    })
    .catch(function(err) {
      console.warn('Retry failed:', err.message);
    });
  };

  function clearPendingResults() {
    localStorage.removeItem('pendingResults_' + getSkill());
  }

  // ============================================================
  // VALIDATION — highlight unanswered questions
  // ============================================================

  function highlightUnanswered(unanswered) {
    document.querySelectorAll('.question.unanswered').forEach(function(el) {
      el.classList.remove('unanswered');
    });

    unanswered.forEach(function(num) {
      var el = document.getElementById('question-' + num);
      if (el) el.classList.add('unanswered');
    });

    if (unanswered.length > 0) {
      var first = document.getElementById('question-' + unanswered[0]);
      if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  // ============================================================
  // SECTION NAVIGATION (listening)
  // ============================================================

  function showSection(n) {
    currentSection = n;
    renderQuestions();
    updateSectionNav();
    updateSectionButtons();
    if (typeof window.onSectionChange === 'function') {
      window.onSectionChange(n);
    }
    var sec = document.getElementById('section-' + n);
    if (sec) sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function updateSectionNav() {
    for (var i = 0; i < getTotalSections(); i++) {
      var step = document.getElementById('section-step-' + i);
      if (!step) continue;
      step.classList.remove('active', 'done');
      if (i < currentSection) step.classList.add('done');
      else if (i === currentSection) step.classList.add('active');

      var connector = document.getElementById('section-connector-' + i);
      if (connector) {
        connector.classList.toggle('done', i < currentSection);
      }
    }
    var label = document.getElementById('section-label');
    if (label) {
      label.textContent = 'Section ' + (currentSection + 1) + ' of ' + getTotalSections();
    }
  }

  function updateSectionButtons() {
    var btnPrev = document.getElementById('btn-prev-section');
    var btnNext = document.getElementById('btn-next-section');
    var btnSubmit = document.getElementById('btn-submit');

    if (btnPrev) btnPrev.style.display = currentSection > 0 ? 'inline-block' : 'none';
    if (btnNext) btnNext.style.display = currentSection < getTotalSections() - 1 ? 'inline-block' : 'none';
    if (btnSubmit) btnSubmit.style.display = currentSection === getTotalSections() - 1 ? 'inline-block' : 'none';
  }

  window.nextSection = function() {
    if (!getSections()) return;
    if (!validateSection()) return;
    if (currentSection < getTotalSections() - 1) {
      showSection(currentSection + 1);
    }
  };

  window.prevSection = function() {
    if (!getSections()) return;
    if (currentSection > 0) {
      showSection(currentSection - 1);
    }
  };

  function validateSection() {
    var collected = collectAnswers();
    if (collected.unanswered.length > 0) {
      highlightUnanswered(collected.unanswered);
      if (unansweredCount) unansweredCount.textContent = collected.unanswered.length;
      if (validationWarning) validationWarning.classList.add('visible');
      setTimeout(function() {
        if (validationWarning) validationWarning.classList.remove('visible');
      }, 3000);
      return false;
    }
    if (validationWarning) validationWarning.classList.remove('visible');
    highlightUnanswered([]);
    return true;
  }

  // ============================================================
  // FORM SUBMIT
  // ============================================================

  if (form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();

      // If multi-section, validate current section first
      if (getSections() && currentSection < getTotalSections() - 1) {
        if (validateSection()) {
          showSection(currentSection + 1);
        }
        return;
      }

      var collected = collectAnswers();

      if (collected.unanswered.length > 0) {
        highlightUnanswered(collected.unanswered);
        if (unansweredCount) unansweredCount.textContent = collected.unanswered.length;
        if (validationWarning) validationWarning.classList.add('visible');
        return;
      }

      if (validationWarning) validationWarning.classList.remove('visible');
      highlightUnanswered([]);

      // Disable form
      var inputs = form.querySelectorAll('input, select, button');
      inputs.forEach(function(el) { el.disabled = true; });

      scoreAnswers(collected.answers).then(function(scoring) {
        showResults(scoring);
        saveResults(scoring);

        // Show transcript if multi-section
        if (getSections() && typeof window.showTranscript === 'function') {
          window.showTranscript();
        }
      }).catch(function(err) {
        console.warn('Scoring failed:', err);
        // Re-enable form on error
        inputs.forEach(function(el) { el.disabled = false; });
      });
    });
  }

  // ============================================================
  // INIT
  // ============================================================

  var pending = localStorage.getItem('pendingResults_' + getSkill());
  if (pending && warningBanner) {
    warningBanner.classList.add('visible');
  }

  renderQuestions();
  if (getSections()) {
    updateSectionNav();
    updateSectionButtons();
  }

  // ============================================================
  // UTILITIES
  // ============================================================

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function arraysEqual(a, b) {
    if (a.length !== b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] !== b[i]) return false;
    }
    return true;
  }

  // Expose for template use
  window.IELTS = {
    renderQuestions: renderQuestions,
    collectAnswers: collectAnswers,
    scoreAnswers: scoreAnswers,
    showResults: showResults,
    saveResults: saveResults,
    showSection: showSection,
    getCurrentSection: function() { return currentSection; },
    getTotalSections: function() { return getTotalSections(); }
  };

})();
