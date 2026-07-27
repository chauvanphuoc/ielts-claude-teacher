# IELTS Scoring Rubrics — Shared Reference

Used by all skills for consistent scoring. Claude reads this to calibrate band scores.

---

## Listening & Reading — Deterministic

| Correct (out of 40) | Band |
|---------------------|------|
| 39-40 | 9.0 |
| 37-38 | 8.5 |
| 35-36 | 8.0 |
| 32-34 | 7.5 |
| 30-31 | 7.0 |
| 26-29 | 6.5 |
| 23-25 | 6.0 |
| 18-22 | 5.5 |
| 16-17 | 5.0 |
| 13-15 | 4.5 |
| 10-12 | 4.0 |

### Scoring Rules

- **Case-insensitive comparison** — "Black Street" = "black street"
- **Whitespace-normalized** — "15 pounds" = "15 pounds" (trim, collapse spaces)
- **Acceptable alternatives** — check answer key's `acceptableAnswers` array
- **Multi-answer (//)** — "roads//road system" → either is correct
- **Pick-from-list** — set comparison, unordered. Over-selection (>pickCount) → 0 for that group
- **Spelling** — minor misspellings that don't change meaning are acceptable UNLESS the answer is a proper noun tested for spelling

---

## Writing — Four Dimensions (0.5-band increments)

### Task Response (TR)

| Band | Descriptor |
|------|-----------|
| 9.0 | Fully addresses all parts, well-developed position, relevant extended ideas |
| 8.5 | Fully addresses all parts, clear position throughout, most ideas well-extended |
| 8.0 | Sufficiently addresses all parts, clear position, well-supported ideas |
| 7.5 | Addresses all parts well, clear position maintained, main ideas extended with some unevenness |
| 7.0 | Addresses all parts, clear position throughout, main ideas extended |
| 6.5 | Addresses all parts but some underdeveloped, position generally clear, some ideas lack support |
| 6.0 | Addresses all parts though some fuller than others, clear position, relevant ideas |
| 5.5 | Addresses the task partially, position present but unclear in places, ideas mixed relevance |
| 5.0 | Addresses the task only partially, position may be unclear, some ideas irrelevant |
| 4.5 | Responds minimally, position hard to identify, ideas repetitive or off-topic in places |
| 4.0 | Responds to task only minimally, position unclear, ideas repetitive |

**Task 1 specifics:** Band 6+ must present an overview. Band 5 lacks a clear overview. Band 4 may misread the data.

**Task 2 specifics:** Band 6+ must present a clear position throughout. Band 5 may have an unclear position. Band 4 may not take a position.

### Coherence & Cohesion (CC)

| Band | Descriptor |
|------|-----------|
| 9.0 | Manages cohesion skillfully, paragraphing is logical |
| 8.5 | Sequences logically with skillful cohesion, paragraphing well-managed |
| 8.0 | Sequences information logically, manages cohesion well, appropriate paragraphing |
| 7.5 | Clear progression throughout, cohesive devices varied and mostly accurate, paragraphing logical |
| 7.0 | Logically organizes information, clear progression, cohesive devices varied |
| 6.5 | Information arranged coherently, adequate cohesive devices, paragraphing present but mechanical at times |
| 6.0 | Arranges information coherently, uses cohesive devices, paragraphing present but may be mechanical |
| 5.5 | Some organization but progression not always clear, cohesive devices limited or repetitive, paragraphing inconsistent |
| 5.0 | Presents information with some organization, inadequate/inaccurate cohesive devices |
| 4.5 | Information loosely organized, basic cohesive devices only, no clear paragraphing |
| 4.0 | Information not coherent, basic cohesive devices only, no paragraphing |

### Lexical Resource (LR)

| Band | Descriptor |
|------|-----------|
| 9.0 | Wide vocabulary with natural control, precise meaning, idiomatic |
| 8.5 | Wide vocabulary with very natural control, conveys precise meaning, rare inaccuracies |
| 8.0 | Wide vocabulary fluently, conveys precise meaning, occasional inaccuracies |
| 7.5 | Good range of vocabulary, some less common items used appropriately, occasional awkward collocation |
| 7.0 | Sufficient vocabulary for variety, some less common items, occasional errors |
| 6.5 | Adequate vocabulary with some range, attempts less common items with mixed success, some spelling errors |
| 6.0 | Adequate vocabulary for the task, attempts less common items, some spelling errors |
| 5.5 | Limited but adequate vocabulary, few attempts at less common items, noticeable spelling/word choice errors |
| 5.0 | Limited vocabulary, adequate for the task, noticeable spelling errors |
| 4.5 | Basic vocabulary, repetitive, word choice errors frequent, spelling errors cause strain |
| 4.0 | Basic vocabulary, repetitive, spelling errors cause difficulty |

### Grammatical Range & Accuracy (GRA)

| Band | Descriptor |
|------|-----------|
| 9.0 | Wide range of structures, flexible and accurate, rare minor errors |
| 8.5 | Wide range used flexibly, vast majority error-free, occasional slips |
| 8.0 | Wide range of structures, majority error-free, occasional inappropriacies |
| 7.5 | Good range of complex structures, frequent error-free sentences, some errors in more complex structures |
| 7.0 | Variety of complex structures, frequent error-free sentences, good control |
| 6.5 | Mix of simple and complex, complex structures attempted, errors present but meaning clear |
| 6.0 | Mix of simple and complex, errors present but don't reduce clarity |
| 5.5 | Limited range, complex structures rare or error-prone, errors sometimes reduce clarity |
| 5.0 | Limited range of structures, errors frequent, some punctuation issues |
| 4.5 | Very limited range, subordinate clauses rare or absent, errors impede meaning in places |
| 4.0 | Very limited range, subordinate clauses rare, errors predominate |

### Overall Writing Band

Average of 4 dimensions: `(TR + CC + LR + GRA) / 4`, rounded to nearest 0.5.

Task 1 weighting: TR scores may be adjusted +0.5 if the overview is particularly strong, or -0.5 if missing entirely.

---

## Speaking — Four Dimensions (0.5-band increments)

### Fluency & Coherence (FC)

| Band | Descriptor |
|------|-----------|
| 9.0 | Speaks fluently with rare hesitation, any hesitation is content-related, develops topics coherently |
| 8.5 | Speaks very fluently, occasional repetition only, hesitation is content-related, topics developed fully |
| 8.0 | Speaks fluently with occasional repetition/self-correction, hesitation is content-related, develops topics coherently |
| 7.5 | Speaks at length comfortably, minor language-related hesitation, uses range of connectives effectively |
| 7.0 | Speaks at length without noticeable effort, may demonstrate language-related hesitation, uses connectives |
| 6.5 | Willing to speak at length, some repetition/self-correction, uses cohesive devices, occasional hesitation |
| 6.0 | Willing to speak at length, noticeable repetition and self-correction, uses some cohesive devices |
| 5.5 | Maintains flow with effort, noticeable hesitation and repetition, limited connectives |
| 5.0 | Maintains flow but noticeable hesitation, limited connectives, simple speech |

**Filler words:** Count "um", "uh", "like", "you know", "I mean", "sort of", "kind of". Band 7+: <2 per minute. Band 6: 2-4/min. Band 5: >4/min.

### Lexical Resource (LR)

| Band | Descriptor |
|------|-----------|
| 9.0 | Uses vocabulary with full flexibility, idiomatic language naturally |
| 8.5 | Very wide resource, paraphrases skillfully, idiomatic usage natural |
| 8.0 | Wide resource readily, paraphrases effectively, conveys meaning skillfully |
| 7.5 | Wide resource, some less common/idiomatic items, effective paraphrasing with minor gaps |
| 7.0 | Flexible use of vocabulary, uses some less common items, effective paraphrasing |
| 6.5 | Adequate range, attempts less common items with mixed success, can paraphrase familiar topics |
| 6.0 | Wide enough vocabulary to discuss topics at length, attempts paraphrasing |
| 5.5 | Sufficient for familiar topics, limited range for unfamiliar topics, paraphrasing attempted but limited |
| 5.0 | Manages talk about familiar topics, limited vocabulary for unfamiliar topics |

### Grammatical Range & Accuracy (GR)

| Band | Descriptor |
|------|-----------|
| 9.0 | Full range of structures, consistently accurate |
| 8.5 | Wide range used flexibly, very high accuracy, occasional slips in complex structures |
| 8.0 | Wide range, flexible use, high proportion of error-free sentences |
| 7.5 | Good range of complex structures, frequently error-free, some errors in less common structures |
| 7.0 | Range of complex structures, frequently error-free, some grammatical mistakes persist |
| 6.5 | Mix of simple and complex, complex structures attempted, errors frequent but meaning not affected |
| 6.0 | Mix of simple and complex structures, errors may be frequent but meaning is clear |
| 5.5 | Limited range, basic complex forms attempted with errors, meaning sometimes affected |
| 5.0 | Basic sentence forms, errors are frequent and may cause comprehension difficulty |

**Common grammar error patterns to flag:** article misuse (a/an/the), tense inconsistency, subject-verb agreement, missing prepositions, word order in questions, conditional forms.

### Pronunciation (Pron)

| Band | Descriptor |
|------|-----------|
| 9.0 | Uses full range of features with precision, effortless to understand |
| 8.5 | Wide range used precisely, easy to understand, accent has no effect on intelligibility |
| 8.0 | Wide range of features, easy to understand throughout, accent has minimal effect |
| 7.5 | Good range of features, generally easy to understand, occasional mispronunciation of less common words |
| 7.0 | Displays features of Band 6 and some of Band 8 |
| 6.5 | Generally intelligible, some mispronunciation, accent requires occasional listener effort |
| 6.0 | Generally intelligible, some mispronunciation of individual words, accent may affect clarity |
| 5.5 | Generally intelligible but mispronunciations cause occasional strain, limited phonological features |
| 5.0 | Generally intelligible, but mispronunciations cause occasional strain for the listener |

**Azure Speech mapping (approximate):**

| Azure PronScore | IELTS Pron Band |
|-----------------|-----------------|
| ≥ 0.90 | 8.0 – 9.0 |
| 0.80 – 0.89 | 7.0 – 7.5 |
| 0.65 – 0.79 | 6.0 – 6.5 |
| 0.50 – 0.64 | 5.0 – 5.5 |
| 0.35 – 0.49 | 4.0 – 4.5 |
| < 0.35 | < 4.0 |

### Overall Speaking Band

Average of 4 dimensions: `(FC + LR + GR + Pron) / 4`, rounded to nearest 0.5.

---

## Error Type Taxonomy

### Listening Errors → KC Mapping

| Error Pattern | KC Tag | Example |
|--------------|--------|---------|
| `spelling` — heard correctly, spelled wrong | `kc-listen-spelling` | "accomodation" → "accommodation" |
| `number-date` — number/date/price confusion | `kc-listen-numbers` | 15 vs 50, £16.50 vs £60.50 |
| `missed` — didn't hear the key information | `kc-listen-gapfill` | left blank on a gap-fill question |
| `distractor` — chose first answer before speaker corrected | `kc-listen-distractor` | "The tour starts at 9am... actually no, 10am" |
| `format` — right answer, wrong format | `kc-listen-gapfill` | exceeded word limit, missing unit |
| `plural` — missing/extra 's' | `kc-listen-spelling` | "student" instead of "students" |
| `MC-paraphrase` — wrong MC option, paraphrase mismatch | `kc-listen-mc` | chose option with similar keywords |
| `map-location` — wrong location on map/diagram | `kc-listen-map` | misidentified spatial reference |
| `inference` — misunderstood speaker's opinion/attitude | `kc-listen-inference` | took sarcasm as literal agreement |
| `pick-from-list-missed` — missed correct option(s) | `kc-listen-mc` | bỏ sót đáp án đúng |
| `pick-from-list-extra` — selected wrong option(s) | `kc-listen-mc` | chọn đáp án sai |
| `pick-from-list-over` — over-selected (>N options) | `kc-listen-mc` | chọn quá số lượng cho phép |

### Reading Errors → KC Mapping

| Error Pattern | KC Tag | Example |
|--------------|--------|---------|
| `T/F/NG-FALSE-vs-NG` — chose FALSE when answer is NOT GIVEN | `kc-read-tfng` | passage doesn't mention, student said FALSE |
| `T/F/NG-TRUE-vs-FALSE` — chose TRUE when passage contradicts | `kc-read-tfng` | passage says opposite, student said TRUE |
| `Y/N/NG-NO-vs-NG` — chose NO when answer is NOT GIVEN | `kc-read-ynng` | author doesn't state opinion, student said NO |
| `headings-mismatch` — wrong paragraph heading matched | `kc-read-headings` | chose heading that fits a different paragraph |
| `MC-distractor` — chose distractor option, paraphrase mismatch | `kc-read-mc` | chose option with similar keywords but wrong meaning |
| `gapfill-wrong-word` — wrong word or exceeded word limit | `kc-read-gapfill` | found right location, wrote wrong word |
| `gapfill-paraphrase` — didn't recognize paraphrased equivalent | `kc-read-gapfill` | searched for keyword, missed paraphrase |
| `matching-error` — wrong match (info/person/date) | `kc-read-matching` | assigned statement to wrong person |
| `vocab-blocked` — unknown word blocked comprehension | `kc-read-vocab-context` | key word not understood, guessed wrong |
| `inference-failed` — required inference not made | `kc-read-inference` | couldn't read between the lines |
| `shortanswer-scope` — misunderstood question scope | `kc-read-detail` | answered a different question |
| `summary-paraphrase` — wrong paraphrase match in summary | `kc-read-summary` | chose wrong word from word list |
| `pick-from-list` — missed/wrong/over-selected in pick-from-list | `kc-read-mc` | similar to listening pick-from-list rules |

### Writing Errors → KC Mapping

| Score Pattern | KC Tag |
|--------------|--------|
| TR < 6.0 — task not fully addressed, missing overview, unclear position | `kc-write-tr` |
| CC < 6.0 — weak paragraphing, limited cohesive devices, no clear progression | `kc-write-cc` |
| LR < 6.0 — limited vocabulary, repetitive word choice, spelling errors | `kc-write-lr` |
| GRA < 6.0 — limited structures, frequent errors, punctuation issues | `kc-write-gra` |
| Article errors prominent | `kc-write-gra-articles` |
| Tense inconsistency prominent | `kc-write-gra-tenses` |
| Complex sentences attempted but error-prone | `kc-write-gra-complex` |

### Speaking Errors → KC Mapping

| Score Pattern | KC Tag |
|--------------|--------|
| FC < 6.0 — hesitation, repetition, limited connectives | `kc-speak-fluency` |
| FC < 6.0 — logical flow issues, weak structure | `kc-speak-coherence` |
| LR < 6.0 — limited vocabulary, no less common items, basic paraphrasing | `kc-speak-lexical` |
| GR < 6.0 — basic sentences, frequent grammar errors | `kc-speak-grammar` |
| Pron < 6.0 — mispronunciation affecting clarity | `kc-speak-pronunciation` |

---

## Vocabulary SRS Integration

Spelling and pronunciation errors from all 4 skills automatically feed into `vocabulary.words` with per-word spaced repetition:

| Error Source | Trigger | CLI Command |
|-------------|---------|------------|
| Listening | Spelling error (proper noun, common word, plural -s) | `vocab add --word X --correct Y --source listening --context "Qn"` |
| Writing | Spelling error in LR scoring | `vocab add --word X --correct Y --source writing --context "Task n"` |
| Speaking | Per-word Azure accuracy < 0.70 | `vocab add --word X --correct X --source speaking --context "Part n"` |
| Reading | N/A (vocabulary-in-context tracked via synonyms) | `synonym add --word X --synonym Y --context "Passage n"` |

**SRS Schedule (same as KC mastery):**

| Attempt | Review After |
|---------|-------------|
| 1 | 1 day |
| 2 | 3 days |
| 3 | 7 days |
| 4+ | 30 days |

**Levels:** `new` (0-1 attempts) → `learning` (2-3) → `mastered` (4+, no new errors)

**Review command:** `.venv/bin/python3 shared/ielts_cli.py vocab review --word X --passed true|false`

---

## Anchor Essay Citation Format

When comparing a student essay to anchor essays during double-scoring, cite anchors by ID:

```
Compared to Anchor cam2-acad-t3t2-band8 (Band 8.0, examiner-verified),
this essay shows [weaker/stronger/similar] [dimension] because [evidence].
```

**Anchor bank:** `.ielts/calibration/writing-anchors.json` — 6 pre-graded essays across Bands 5.0-9.0.

| Anchor ID | Band | Task | Confidence |
|-----------|------|------|-----------|
| `eval-band5.0-t2` | 5.0 | Task 2 | verified |
| `eval-band6.5-t2` | 6.5 | Task 2 | verified |
| `cam2-acad-t3t1-band7` | 7.0 | Task 1 | examiner |
| `cam2-acad-t3t2-band8` | 8.0 | Task 2 | examiner |
| `eval-band8.0-t2` | 8.0 | Task 2 | verified |
| `cam2-acad-t1t2-band9` | 9.0 | Task 2 | examiner |
