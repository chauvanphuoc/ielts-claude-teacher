# Web Research for Mini Test Creation

## CODE BOUNDARY (invariant)

- Agent MAY READ data: `.ielts/**`, `shared/**/*.json`, `shared/**/*.md`,
  `textbook/**/*.md`, `phases/*.md`.
- Agent MAY READ for rendering/grading: `*.html`, `*.css`, `templates/**`
  (reading HTML to render tests or evaluate answers — system workflow, kept intact).
- Agent MUST NOT READ code: all `.py`, `.js`, `server.py`, `ielts_cli.py`,
  `generate_test_html.py`, `pronounce_cli.py`, `extract_listening.py`.
  Code is a black box — only run via CLI commands documented in this SKILL.
- Agent MUST NOT EDIT: any code file (especially `.py` and `.js`). Code errors
  → report the error + invite user to run `/developer-ielts-sys`.
- Missing CLI/renderer → report to user, DO NOT craft HTML/JS by hand.
- Data that MAY be edited: `.ielts/**`, `shared/**/*.json`, `textbook/**/*.md`.

---

## Overview

This phase adds an optional but preferred web research step to mini-test creation. Instead of relying solely on Claude's internal knowledge or local Cambridge JSON, the teacher searches for real, current articles from high-quality academic sources to use as authentic question material.

**Principle:** Web content is PREFERRED but NOT MANDATORY. If web search fails after 2 attempts, fall back to existing behavior (Cambridge JSON or Claude knowledge) — seamlessly, without delaying the student.

---

## Hybrid Fetch Strategy

Different sources require different access methods due to anti-bot protections:

| Source | Method | What You Get | Quality |
|--------|--------|-------------|---------|
| **TheConversation.com** | `WebFetch` | Full article text (verbatim) | ⭐⭐⭐ Excellent — verbatim paragraphs, exact quotes, real data |
| **Aeon.co** | `WebSearch` | Detailed summary from search index | ⭐⭐ Good — thesis, key claims, specific details, expert names; NO verbatim paragraphs |

**Why the difference:** Aeon.co uses Cloudflare anti-bot protection which blocks automated HTTP requests (WebFetch returns HTTP 429). However, WebSearch can still access Aeon content through its search index, returning rich summaries with enough detail for question creation.

---

## Sources

### Aeon.co — via WebSearch

| Attribute | Value |
|-----------|-------|
| Access method | `WebSearch` (NOT WebFetch — blocked by Cloudflare) |
| Query pattern | `aeon.co essay {topic_keywords}` |
| Content type | Long-form essays, deep analysis |
| Best for domains | Philosophy, culture, science, psychology, ethics, art |
| Writing style | Academic, argumentative, multi-layered |
| What you get | Article title, author, thesis, 4-6 key observations/claims, specific names/places/data, expert quotes (paraphrased), conclusion |
| What you DON'T get | Verbatim paragraphs, exact sentence wording |

**Why Aeon for IELTS:** Aeon essays have clear thesis statements, writer opinions, nuanced arguments, and academic vocabulary — ideal for inference, T/F/NG, Y/N/NG, and main-idea questions. The multi-layered writing style mirrors the complexity of IELTS Reading passages. WebSearch summaries preserve enough detail (thesis + key claims + specific data + expert names) to create authentic-feeling questions.

**Example WebSearch query:**
```
WebSearch query="aeon.co essay environment health elephants scarcity"
```
Returns: article title, author (Caitlin O'Connell-Rodwell), thesis about matriarchal elephant families under scarcity, 4-6 specific observations (Zeta's expulsion, Baby Groot's care, Warrior family aggression), location details (Etosha National Park, Namibia, Mushara waterhole), theoretical framework (optimal foraging theory), and the human-parallel conclusion.

### The Conversation — via WebFetch

| Attribute | Value |
|-----------|-------|
| Access method | `WebFetch` (full HTML → markdown) |
| URL pattern | `https://theconversation.com/global/search?q={url_encoded_topic}&sort=relevancy&language=en&date=all` |
| Content type | Evidence-based analysis, expert commentary |
| Best for domains | Education, health, economy, policy, environment, technology |
| Writing style | Journalistic-academic, accessible, data-rich |
| What you get | Full article text — verbatim paragraphs, exact quotes, real statistics |

**Why The Conversation for IELTS:** Articles contain specific data points, expert quotes, clear section structure, and accessible academic language — ideal for detail-locating, gap-fill, matching, and multiple-choice questions. The evidence-based style provides rich verbatim material for distractors. Full text is always freely accessible.

---

## KC → Source Mapping

### Aeon.co — Preferred for these KCs

| KC | Rationale |
|----|-----------|
| `kc-read-main-idea` | Aeon essays have clear, well-developed thesis statements |
| `kc-read-inference` | Multi-layered writing with rich implications |
| `kc-read-tfng` | Strong factual claims + nuanced arguments — good for TRUE/FALSE/NOT GIVEN traps |
| `kc-read-ynng` | Writer's opinions and claims are explicit and well-argued |
| `kc-read-vocab-context` | Rich academic vocabulary in natural context |
| `kc-speak-coherence` | Deep discussion topics for Speaking Part 3 |
| `kc-write-cc` | Model argument structures for Writing Task 2 |

### The Conversation — Preferred for these KCs

| KC | Rationale |
|----|-----------|
| `kc-read-detail` | Rich with specific data, statistics, expert names (verbatim) |
| `kc-read-gapfill` | Data-dense paragraphs ideal for gap-fill exercises |
| `kc-read-matching` | Clear multi-section structure |
| `kc-read-mc` | Factual content with natural distractor candidates |
| `kc-write-tr` | Policy/social analysis as models for Task 2 |
| `kc-write-lr` | Diverse academic vocabulary in context |
| `kc-speak-lexical` | Topic-specific vocabulary in context |

### Override: Student mentions specific domain

| Student says | Source |
|-------------|--------|
| Triết học, văn hóa, nghệ thuật, tâm lý, đạo đức | Aeon.co |
| Giáo dục, sức khỏe, kinh tế, chính sách, môi trường | TheConversation.com |
| "Bài nào cũng được" / không đề cập chủ đề | Follow KC→Source mapping above |

---

## Search Flow

### Step 1 — Determine topic keywords

From conversation context + KC, extract 1-2 English keywords:

```
KC = kc-read-inference, student: "con thích đọc về môi trường"
→ keywords: "environment climate"

KC = kc-write-tr, student: "con yếu phân tích kinh tế"
→ keywords: "economic policy"

KC = kc-read-tfng, no student topic preference
→ keywords: from KC exerciseTemplates + common IELTS topics (technology, education, health, etc.)
```

**Topic ideas by KC (when student has no preference):**

| KC | Suggested topics |
|----|-----------------|
| `kc-read-tfng` | artificial intelligence ethics, climate policy, education reform |
| `kc-read-ynng` | social media impact, remote work, cultural globalization |
| `kc-read-inference` | philosophy of science, psychology of decision-making |
| `kc-read-detail` | public health data, economic indicators, demographic trends |
| `kc-read-gapfill` | scientific discoveries, historical events, technological innovations |
| `kc-write-tr` | government spending, urban planning, healthcare systems |
| `kc-write-cc` | argument structure: technology in education, art funding |

### Step 2 — Search (method depends on source)

#### Path A: TheConversation.com → WebFetch

```
1. Construct URL:
   https://theconversation.com/global/search?q={url_encode(keywords)}&sort=relevancy&language=en&date=all

2. WebFetch search page:
   WebFetch url="{search_url}" prompt="List the top 5 article results with title, URL, and one-line description. Flag anything that is a video, podcast, or not a full article."

3. Pick best 2-3 articles (see selection criteria below)

4. WebFetch each article:
   WebFetch url="{article_url}" prompt="Extract: 1) Main argument (2-3 sentences), 2) 2-4 key paragraphs (200-400 words, verbatim), 3) Specific data/statistics/expert quotes with exact wording. Preserve original text."
```

#### Path B: Aeon.co → WebSearch

```
1. Construct query:
   "aeon.co essay {topic_keywords}"

2. WebSearch:
   WebSearch query="aeon.co essay {topic_keywords}"

3. From search results, identify the best Aeon article:
   - Look for the result with "aeon.co/essays/" in the URL
   - Read the summary provided by search index
   - Note: you CANNOT WebFetch the URL (will 403/429) — use the summary as-is

4. Extract from the summary:
   - Article title, author, publication context
   - Thesis / main argument
   - 4-6 key observations or claims
   - Specific names, places, dates, data points mentioned
   - Theoretical frameworks or expert references
   - Conclusion or human-parallel statements

5. The summary IS your source material — it contains enough detail to create:
   - T/F/NG statements (claims can be verified against the summary)
   - Y/N/NG statements (writer's opinions are captured)
   - MC questions (thesis + supporting details as distractors)
   - Gap-fill items (specific names, dates, data points)
```

### Step 3 — Pick articles (selection criteria)

- [ ] From Aeon or TheConversation (not aggregated/republished content)
- [ ] Academic but accessible tone (IELTS band 5.5-8.0 range)
- [ ] Clear thesis or argument structure — not just news reporting
- [ ] Contains specific data, examples, or expert quotes
- [ ] **TheConversation:** ~800-2000 words (substantial enough for 5 questions)
- [ ] **Aeon:** summary must include 4+ distinct claims/observations (enough for 5 questions)
- [ ] **Aeon:** the `aeon.co/essays/` URL is accessible (not paywalled — essay section is free)

### Step 4 — Extract question material

#### From TheConversation (verbatim)

1. **Passage excerpt:** 2-4 paragraphs (200-400 words) — verbatim text students will read
2. **Thesis statement:** 1 sentence — the article's main argument (can be verbatim)
3. **Key claims:** 3-5 factual claims — in the article's own words
4. **Writer's opinions:** 2-3 opinion statements — for Y/N/NG questions
5. **Data points:** specific numbers, dates, names — verbatim for gap-fill `correctAnswer`
6. **Metadata:** title, author, source domain, URL, publication date

#### From Aeon (summary-based)

1. **Passage excerpt:** Write a coherent 150-250 word passage synthesizing the key observations from the summary. Use academic tone. Base every sentence on a specific detail from the summary — do NOT invent. This becomes the reading passage.
2. **Thesis statement:** 1 sentence — from the summary (paraphrase if needed)
3. **Key claims:** 3-5 factual claims derived from the summary's observations
4. **Writer's opinions:** 2-3 opinion statements — from the author's conclusions/arguments
5. **Data points:** specific names, places, dates mentioned in the summary — for gap-fill
6. **Metadata:** title, author, source domain, URL

**⚠️ Aeon fidelity rule:** Every claim, data point, and name in your synthesized passage MUST trace to a specific detail in the WebSearch summary. If the summary doesn't mention a fact, don't add it. The synthesized passage should read like a condensed version of the article — accurate, coherent, but NOT verbatim.

---

## Content Quality Checklist

Before proceeding to question creation, verify:

### TheConversation (verbatim)
- [ ] Article is from TheConversation.com (original content)
- [ ] Academic but accessible tone — not too technical, not too casual
- [ ] Clear thesis or argument structure
- [ ] Contains specific data, examples, or expert quotes
- [ ] 200-400 words extracted verbatim
- [ ] Full text was accessible (no paywall, no 403, no timeout)
- [ ] Content is self-contained — the excerpt makes sense without the full article

### Aeon (summary-based)
- [ ] Article is from aeon.co/essays/ (not aggregated/republished)
- [ ] WebSearch summary includes 4+ distinct claims/observations
- [ ] Summary includes specific names, places, or data points
- [ ] Synthesized passage is 150-250 words, academic tone
- [ ] Every fact in the passage traces to a detail in the WebSearch summary
- [ ] No invented facts — fidelity maintained
- [ ] Passage is self-contained and coherent

---

## Extraction Guidelines by Question Type

### For T/F/NG and Y/N/NG

**TheConversation (verbatim):** Pick paragraphs with clear factual claims. TRUE = directly supported, FALSE = contradicted by the text, NOT GIVEN = plausible but unmentioned.

**Aeon (summary-based):** Use the key observations from the summary as TRUE statements. Create FALSE by inverting a claim. Create NOT GIVEN by making a plausible extension the article doesn't address. Example from the elephant essay:
- TRUE: "Elephant family dynamics change under conditions of environmental scarcity"
- FALSE: "Zeta was expelled from her family because of aggressive behavior toward the matriarch" (summary says: because of resource scarcity / optimal foraging)
- NOT GIVEN: "The elephant families at Mushara waterhole have been studied for over 50 years" (summary says 33 years, but doesn't rule out longer study)

### For Multiple Choice

**TheConversation (verbatim):** Main point → correct answer. Supporting details → distractors using `commonErrors` patterns.

**Aeon (summary-based):** Thesis statement → correct answer. Individual observations → distractors (one observation as a distractor, another as correct — student must identify which is the main argument vs supporting detail).

### For Gap-Fill

**TheConversation (verbatim):** Blank out specific data (numbers, dates, names). `correctAnswer` = exact text from article. Include `acceptableAnswers` with variations.

**Aeon (summary-based):** Blank out key names (Zeta, Mushara, Etosha), numbers (33 years), or technical terms (optimal foraging theory). Use the exact spelling from the summary. Include `acceptableAnswers`. The synthesized passage must provide enough context clues for the student to infer the answer.

### For Matching Headings

**TheConversation (verbatim):** Use the article's natural section structure.

**Aeon (summary-based):** Group the key observations into 3-4 thematic sections. Create headings that match each group. Include extra headings that match only partially (common trap).

---

## Fallback Strategy

Web research can fail for many reasons. Handle gracefully:

### Level 0: Primary source works
→ Use as described above. This is the happy path.

### Level 1: Primary source partially fails
- **Aeon WebSearch returns no good results:** Switch to TheConversation with the same topic. TheConversation also covers philosophy/psychology topics — find the closest angle.
- **TheConversation WebFetch fails (rare):** Switch to Aeon WebSearch with the same topic.

### Level 2: Both sources fail for the topic
→ Broaden keywords, try once more. If still nothing → Level 3.

### Level 3: No web access at all
→ Use Cambridge JSON from `shared/` or `textbook/` directories (existing behavior)
→ Or create questions from Claude's own IELTS knowledge (existing behavior)
→ Tell student: "I created this test from Cambridge materials." — no need to mention web search failure

**⚠️ CRITICAL RULES:**
- Max 2 search attempts per test — do NOT spend more than 60 seconds on web research
- Fallback is NORMAL and EXPECTED — web content is a bonus, not a requirement
- Never delay the student because of web issues
- Never pass summary-based content off as verbatim — be transparent about source type

---

## Attribution Format

### When using TheConversation (verbatim)

```html
<div class="source-attribution">
  <span class="source-label">Source:</span>
  <a href="{ARTICLE_URL}" target="_blank" rel="noopener">{ARTICLE_TITLE}</a>
  <span class="source-author">by {AUTHOR}</span>
  <span class="source-domain">The Conversation</span>
</div>
```

### When using Aeon (summary-based)

```html
<div class="source-attribution">
  <span class="source-label">Source:</span>
  <a href="{ARTICLE_URL}" target="_blank" rel="noopener">{ARTICLE_TITLE}</a>
  <span class="source-author">by {AUTHOR}</span>
  <span class="source-domain">Aeon</span>
</div>
```

### When using fallback

`{{SOURCE_ATTRIBUTION_HTML}}` → `""` (empty string). Never fabricate attribution.

**Placeholder:** `{{SOURCE_ATTRIBUTION_HTML}}` — set to the appropriate HTML above when web content is used, or empty string `""` when using fallback.

---

## Quick Reference Card

```
Web Research — Hybrid Quick Steps:

TheConversation path (verbatim):
  1. Topic keywords ← conversation context + KC
  2. WebFetch search URL → pick 2-3 articles
  3. WebFetch article URL → extract 200-400 verbatim words
  4. Create questions from exact text
  5. Build {{SOURCE_ATTRIBUTION_HTML}}

Aeon path (summary-based):
  1. Topic keywords ← conversation context + KC
  2. WebSearch "aeon.co essay {keywords}" → read summary
  3. Verify 4+ distinct claims in summary
  4. Synthesize 150-250 word passage from summary details
  5. Create questions from synthesized passage (fidelity rule!)
  6. Build {{SOURCE_ATTRIBUTION_HTML}}

Either path fails → retry once → fail again → Cambridge JSON fallback
```
