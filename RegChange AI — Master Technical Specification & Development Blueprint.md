# RegChange AI — Master Technical Specification & Development Blueprint

## 1. PROJECT IDENTITY

**Project Name:** RegChange AI

**Project Type:** AI-Powered Regulatory Circular Comparison and Change Intelligence Platform

**Primary Domain:** RBI Circulars / Regulatory Documents

**Primary Use Case:** Compare two versions of regulatory circulars and identify, categorize, explain, prioritize, and trace every meaningful change introduced in the newer version.

**Current Input Scenario:**

- Previous RBI circular: approximately 59 pages
- New RBI circular: approximately 100 pages
- Local Llama 3.2 8B model available
- Processing should preferably remain local/private
- The system must produce auditable, traceable results rather than opaque LLM-generated conclusions.

---

# 2. CORE OBJECTIVE

Build an AI-powered regulatory intelligence system that can compare two versions of RBI circulars at **section, clause, paragraph, sentence, table, and semantic levels**.

The system must determine:

1. What was added?
2. What was removed?
3. What was modified?
4. What was relocated or renumbered?
5. What was merely reworded?
6. What regulatory requirement became stricter or more relaxed?
7. What thresholds, limits, dates, percentages, conditions, or obligations changed?
8. What new compliance requirements were introduced?
9. Which changes have the highest operational impact?
10. Which stakeholders are affected?
11. Where exactly did the change occur?
12. What evidence supports the detected change?
13. How confident is the system?
14. Can a human reviewer verify the conclusion immediately?

The system MUST NOT behave as a generic PDF summarizer.

It must behave as a **Regulatory Change Detection and Decision-Support Engine**.

---

# 3. PROBLEM STATEMENT

Regulatory institutions frequently publish revised circulars, notifications, guidelines, directions, FAQs, and amendments.

A human analyst comparing two long versions manually must:

- read both documents,
- identify corresponding sections,
- account for renumbered clauses,
- identify additions,
- identify deletions,
- detect subtle wording changes,
- compare numerical values,
- understand changed obligations,
- distinguish substantive changes from editorial changes,
- trace every conclusion back to the source.

For a 59-page versus 100-page circular, manually performing this comparison is slow, error-prone, and difficult to audit.

A naive text-diff system also fails because:

- paragraphs can move,
- sections can be renumbered,
- sentences can be rewritten without changing meaning,
- tables can change,
- wording can change while the obligation remains identical,
- one old paragraph can become multiple new paragraphs,
- multiple old paragraphs can be consolidated,
- new requirements may appear in completely new sections.

Therefore, RegChange AI must combine:

**Structural Parsing + Deterministic Diffing + Semantic Matching + Numerical Comparison + LLM Reasoning + Evidence Traceability + Human Review.**

---

# 4. BASELINE REQUIREMENTS — NON-NEGOTIABLE

The following capabilities are mandatory and constitute the MVP.

## BR-01 — Dual Document Upload

The system MUST allow users to upload:

- Old circular PDF
- New circular PDF

Supported formats should initially include:

- PDF
- OCR-based/scanned PDF

Future support:

- DOCX
- HTML
- RBI webpage URLs

---

## BR-02 — Document Preprocessing

The system MUST:

- extract text,
- preserve page numbers,
- preserve headings,
- detect sections,
- detect subsections,
- detect numbered clauses,
- detect paragraphs,
- detect tables where possible,
- preserve document hierarchy,
- identify headers and footers,
- remove irrelevant repeated content.

Every extracted unit should maintain provenance.

Example:

```json
{
  "document_id": "OLD_RBI_001",
  "page": 24,
  "section": "4.2",
  "clause": "4.2.3",
  "text": "...",
  "source_type": "paragraph"
}
```

---

# 5. DOCUMENT NORMALIZATION

The system MUST normalize documents before comparison.

Normalization includes:

- whitespace normalization,
- line-break normalization,
- hyphenation correction,
- repeated header removal,
- repeated footer removal,
- page-number removal from semantic text,
- Unicode normalization,
- OCR artifact correction,
- character encoding normalization.

However, normalization MUST NOT destroy regulatory meaning.

For example:

```text
₹ 10 lakh
₹10 lakh
Rs. 10 lakh
INR 10 lakh
```

should be recognized as semantically equivalent representations.

---

# 6. HIERARCHICAL DOCUMENT MODEL

Do not represent the circular as one giant text string.

Represent it as:

```text
Document
│
├── Chapter
│   ├── Section
│   │   ├── Subsection
│   │   │   ├── Clause
│   │   │   │   ├── Paragraph
│   │   │   │   └── Table
│   │   │   └── Clause
│   │   └── Section
│   └── Chapter
│
└── Annexure
    ├── Table
    └── Clause
```

Each node MUST contain:

```json
{
  "node_id": "...",
  "document_version": "old",
  "page_start": 12,
  "page_end": 13,
  "section_number": "3.4",
  "heading": "Reporting Requirements",
  "parent_id": "...",
  "text": "...",
  "content_type": "clause"
}
```

This hierarchical representation is fundamental to accurate comparison.

---

# 7. CHANGE DETECTION ENGINE

The comparison engine MUST use multiple levels of comparison.

## Layer 1 — Exact Matching

Compare:

- section numbers,
- headings,
- normalized text,
- exact phrases.

Useful for obvious matches.

---

## Layer 2 — Structural Matching

Match clauses using:

- section number,
- heading similarity,
- parent section,
- document position,
- neighboring clauses.

Example:

```text
OLD:
4.2 Reporting Requirements

NEW:
5.1 Reporting Requirements
```

Even though numbering changed, the system should identify them as probable counterparts.

---

## Layer 3 — Lexical Similarity

Use:

- TF-IDF,
- BM25,
- token similarity,
- fuzzy matching.

This handles moderate wording changes.

---

## Layer 4 — Semantic Matching

Generate embeddings for clauses.

Use a local embedding model where possible.

Calculate:

```text
Cosine Similarity(old_clause, new_clause)
```

This allows the system to recognize:

```text
OLD:
The regulated entity shall submit the statement within thirty days.

NEW:
The regulated entity shall furnish the statement within fifteen days.
```

as corresponding clauses despite textual differences.

---

# 8. MANY-TO-MANY CLAUSE ALIGNMENT

This is a critical advanced requirement.

The system MUST support:

### One-to-one

```text
Old Clause A → New Clause A
```

### One-to-many

```text
Old Clause A
      ↓
New Clause A
New Clause B
```

### Many-to-one

```text
Old Clause A ─┐
              ├──→ New Clause B
Old Clause B ─┘
```

### Removed

```text
Old Clause A → No Match
```

### Added

```text
No Old Match → New Clause A
```

This is much stronger than a simple line-by-line diff.

---

# 9. CHANGE CLASSIFICATION TAXONOMY

Every detected change MUST be classified.

Primary categories:

### C01 — Added Requirement

A new regulatory requirement appears.

### C02 — Removed Requirement

An existing requirement has disappeared.

### C03 — Modified Requirement

An existing requirement has materially changed.

### C04 — Threshold / Limit Change

Examples:

- ₹10 lakh → ₹25 lakh
- 10% → 15%
- 30 days → 15 days

### C05 — Timeline Change

Examples:

- reporting deadline,
- implementation date,
- transition period,
- renewal period.

### C06 — Eligibility Change

Who qualifies or does not qualify has changed.

### C07 — Compliance Requirement

New or modified compliance obligations.

### C08 — Reporting Requirement

New or modified reporting obligations.

### C09 — Documentation Requirement

New documents, records, certificates, or evidence required.

### C10 — Penalty / Consequence

Changes involving penalties, restrictions, consequences, or enforcement.

### C11 — Scope Change

The population, institution, transaction, activity, or circumstance covered by the circular changes.

### C12 — Definition Change

A defined regulatory term has changed.

### C13 — Exception / Exemption Change

An exemption or exception has been added, removed, or modified.

### C14 — Procedural Change

The process for complying with a requirement has changed.

### C15 — Reference / Cross-Reference Change

References to another circular, section, regulation, or document have changed.

### C16 — Clarification

Meaning is clarified without materially changing the requirement.

### C17 — Editorial Change

Formatting, grammar, numbering, or wording changes without substantive regulatory impact.

---

# 10. SUBSTANTIVE VS NON-SUBSTANTIVE CHANGE

This distinction is mandatory.

The system must NOT report every textual difference as a regulatory change.

Example:

```text
OLD:
"The bank shall submit the report..."

NEW:
"The Bank shall submit the report..."
```

This is:

```text
Change: Yes
Substantive: No
Category: Editorial
```

Whereas:

```text
OLD:
within 30 days

NEW:
within 15 days
```

is:

```text
Change: Yes
Substantive: Yes
Category: Timeline Change
Impact: High
```

---

# 11. NUMERICAL CHANGE DETECTION ENGINE

Build a dedicated numerical comparison layer.

The system MUST extract and compare:

- monetary amounts,
- percentages,
- dates,
- durations,
- frequencies,
- thresholds,
- limits,
- ratios,
- quantities,
- minimum/maximum values.

Example:

```text
OLD:
₹10 crore

NEW:
₹25 crore
```

Output:

```json
{
  "change_type": "THRESHOLD_CHANGE",
  "old_value": "₹10 crore",
  "new_value": "₹25 crore",
  "direction": "INCREASE",
  "magnitude": "150%",
  "impact": "HIGH"
}
```

The LLM should explain the impact, but the numerical extraction and arithmetic should be deterministic.

---

# 12. OBLIGATION STRENGTH ANALYSIS

The system should detect changes in regulatory language.

Important terms include:

```text
may
should
shall
must
required
permitted
prohibited
not permitted
recommended
mandatory
subject to
unless
except
provided that
```

For example:

```text
OLD:
The entity may submit...

NEW:
The entity shall submit...
```

This should be flagged as a potential **obligation-strengthening change**.

Similarly:

```text
OLD:
shall

NEW:
may
```

should be flagged as a potential relaxation.

The LLM must explain the change while the final classification should remain evidence-backed.

---

# 13. CHANGE IMPACT ENGINE

Every substantive change should receive an impact level:

```text
CRITICAL
HIGH
MEDIUM
LOW
INFORMATIONAL
```

Impact factors:

- mandatory obligation introduced,
- mandatory obligation removed,
- deadline shortened,
- financial threshold changed,
- eligibility expanded/restricted,
- reporting burden increased,
- documentation burden increased,
- penalty changed,
- scope expanded,
- exemption removed.

The system should calculate impact using a deterministic rules engine first and use Llama to provide the natural-language explanation.

---

# 14. REGULATORY CHANGE OBJECT

Every detected change should be represented using a standard schema.

```json
{
  "change_id": "CHG-001",
  "change_type": "MODIFIED",
  "category": "TIMELINE_CHANGE",
  "sub_category": "REPORTING_DEADLINE",
  "impact": "HIGH",
  "confidence": 0.96,

  "old_reference": {
    "page": 24,
    "section": "4.2",
    "clause": "4.2.3",
    "text": "..."
  },

  "new_reference": {
    "page": 31,
    "section": "5.1",
    "clause": "5.1.2",
    "text": "..."
  },

  "change_summary": "...",
  "old_requirement": "...",
  "new_requirement": "...",
  "impact_explanation": "...",

  "evidence": [
    "old_text",
    "new_text"
  ]
}
```

This object becomes the central data contract of the entire system.

---

# 15. LLAMA 3.2 8B ROLE

Llama 3.2 8B MUST NOT be responsible for blindly comparing entire 59-page and 100-page documents.

Instead, it should operate on **small, evidence-grounded comparison units**.

Input:

```text
OLD CLAUSE:
...

NEW CLAUSE:
...

CONTEXT:
Old Section: ...
New Section: ...

TASK:
Determine whether the change is substantive.
Classify it.
Explain its impact.
Return structured JSON.
```

Llama should perform:

- semantic interpretation,
- change classification,
- obligation analysis,
- impact explanation,
- ambiguity detection,
- concise summaries.

---

# 16. STRICT LLM GUARDRAILS

The model MUST:

1. Never invent a requirement.
2. Never invent a section number.
3. Never invent a page number.
4. Never infer a change without evidence.
5. Never modify source text.
6. Never claim a clause changed if no evidence exists.
7. Never generate unsupported legal conclusions.
8. Never treat editorial changes as regulatory changes.
9. Return structured JSON.
10. Provide evidence for every conclusion.
11. Explicitly mark uncertain comparisons.
12. Abstain when evidence is insufficient.

Required principle:

```text
NO EVIDENCE → NO CHANGE CLAIM
```

---

# 17. CONFIDENCE ENGINE

Every change should have a confidence score.

Confidence should consider:

```text
Structural Match
+
Lexical Similarity
+
Semantic Similarity
+
Numerical Agreement
+
LLM Confidence
+
Evidence Quality
```

Example:

```text
Confidence: 97%
```

But confidence MUST NOT simply be whatever number Llama generates.

The platform should calculate its own confidence score.

---

# 18. HUMAN-IN-THE-LOOP REVIEW

Introduce a review queue.

Changes with:

```text
Confidence < 80%
```

or:

```text
Impact = CRITICAL
```

should optionally require human validation.

Reviewer actions:

```text
Accept
Reject
Edit Classification
Mark as Editorial
Mark as Substantive
Add Comment
```

This creates a feedback loop for improving the system.

---

# 19. EVIDENCE-FIRST UI

The most important screen should be a **Change Explorer**.

Example:

```text
┌────────────────────────────────────────────────────┐
│ CHANGE #024                        HIGH IMPACT      │
├────────────────────────────────────────────────────┤
│ Category: Reporting Deadline                       │
│ Confidence: 96%                                    │
├────────────────────┬───────────────────────────────┤
│ OLD VERSION        │ NEW VERSION                   │
│ Page 24            │ Page 31                       │
│ Section 4.2        │ Section 5.1                   │
│                    │                               │
│ "within 30 days"   │ "within 15 days"              │
├────────────────────┴───────────────────────────────┤
│ AI INTERPRETATION                                  │
│ Reporting deadline has been reduced from 30 to     │
│ 15 days. This increases the reporting frequency    │
│ burden on affected entities.                      │
├────────────────────────────────────────────────────┤
│ [Accept] [Reject] [Mark Editorial] [Comment]       │
└────────────────────────────────────────────────────┘
```

The user should never have to trust a black-box score.

---

# 20. SIDE-BY-SIDE DOCUMENT VIEW

Provide:

```text
OLD DOCUMENT                 NEW DOCUMENT

Page 24                      Page 31
Section 4.2                  Section 5.1

[original text]              [new text]

       ← linked →
```

When the user clicks a change, both source locations should be highlighted.

---

# 21. EXECUTIVE CHANGE DASHBOARD

The dashboard should provide:

### Total Changes

```text
47
```

### Substantive Changes

```text
31
```

### Added

```text
12
```

### Removed

```text
4
```

### Modified

```text
15
```

### Editorial

```text
16
```

### High/Critical Impact

```text
9
```

---

# 22. CATEGORY DISTRIBUTION

Visualize:

```text
Reporting          ███████████
Compliance         █████████
Timeline           ██████
Eligibility        █████
Documentation      ████
Definitions        ███
Editorial          ███████████
```

Allow filtering.

---

# 23. IMPACT HEATMAP

Create a matrix:

| Category | Critical | High | Medium | Low |
|---|---:|---:|---:|---:|
| Compliance | 2 | 5 | 3 | 1 |
| Reporting | 1 | 4 | 2 | 2 |
| Timeline | 2 | 3 | 1 | 0 |
| Eligibility | 1 | 2 | 2 | 0 |

Clicking any cell opens the corresponding changes.

---

# 24. CHANGE TIMELINE

If the circular contains effective dates or implementation dates, build:

```text
Publication
     │
     ▼
Transition Period
     │
     ▼
Effective Date
     │
     ▼
Compliance Deadline
```

This solves a real-world problem: users often need to know not merely **what changed**, but **when they must act**.

---

# 25. "WHAT DO I NEED TO DO?" ENGINE

This should become one of the strongest future features.

Transform regulatory changes into action-oriented implications.

Example:

```text
REGULATORY CHANGE
↓
A reporting deadline changed from X to Y
↓
AFFECTED ENTITY
Banks / NBFCs / applicable entities
↓
ACTION
Update reporting workflow
↓
OWNER
Compliance / Regulatory Reporting Team
↓
DEADLINE
Relevant effective date
↓
PRIORITY
HIGH
```

The system should clearly label this as **AI-generated decision support**, not legal advice.

---

# 26. REQUIREMENT REGRESSION ENGINE

Create a normalized "regulatory requirement database".

Instead of storing only documents, store requirements:

```text
Requirement R-1024

Status:
ACTIVE

Source:
Circular Version 3

Requirement:
...

Introduced:
Version 2

Modified:
Version 3

Current State:
...
```

When another circular is uploaded, the system can determine:

```text
Existing Requirement
        ↓
Still Active?
        ↓
Modified?
        ↓
Removed?
        ↓
Reintroduced?
```

This transforms the system from a PDF comparator into a **regulatory knowledge system**.

---

# 27. CROSS-REFERENCE GRAPH

Build a graph of relationships between:

```text
Circular
   ↓
Section
   ↓
Requirement
   ↓
Referenced Circular
   ↓
Regulation
   ↓
Annexure
```

Example:

```text
Circular A
   │
   ├── modifies → Circular B
   │
   ├── supersedes → Circular C
   │
   └── references → Regulation D
```

This solves a major real-world problem: regulatory documents rarely exist in isolation.

---

# 28. SUPERSESSION DETECTION

Detect phrases such as:

```text
supersedes
replaces
amends
withdraws
rescinds
in supersession of
shall cease to apply
with effect from
```

The system should create a regulatory lineage:

```text
Version 1
   ↓
Version 2
   ↓
Version 3
   ↓
Current Version
```

---

# 29. REGULATORY VERSION CONTROL

Every uploaded circular becomes a versioned artifact.

```text
Circular:
ABC/2026-27

Version 1
Version 2
Version 3

Current:
Version 3
```

Users can compare:

```text
V1 → V2
V2 → V3
V1 → V3
```

This is far more powerful than only comparing two PDFs.

---

# 30. "WHAT CHANGED SINCE LAST REVIEW?" FEATURE

For compliance teams:

```text
Last reviewed:
01 August 2026

Current review:
13 August 2026
```

The system should display only newly relevant changes.

This prevents compliance teams from rereading entire circulars repeatedly.

---

# 31. REGULATORY CHANGE DIGEST

Generate a concise operational digest:

```text
5 Critical Changes
11 High Impact Changes
7 Reporting Changes
4 Timeline Changes
```

Each item must link back to evidence.

No unsupported summarization.

---

# 32. ROLE-SPECIFIC IMPACT

Allow the user to choose:

```text
Compliance Officer
Risk Team
Legal Team
Operations
Technology
Finance
Senior Management
```

Then explain changes from that perspective.

Example:

### For Technology

```text
New reporting requirement may require changes
to the existing reporting pipeline.
```

### For Compliance

```text
Reporting frequency has changed and internal
compliance calendars should be reviewed.
```

The underlying regulatory evidence remains identical.

---

# 33. SMART SEARCH

Allow natural-language queries:

```text
"Show me all new reporting requirements."

"Which deadlines changed?"

"Which requirements became stricter?"

"Show all monetary threshold changes."

"What changed for NBFC reporting?"

"Show high-impact changes only."
```

The answer must always include source references.

---

# 34. NATURAL-LANGUAGE REGULATORY QUERY ENGINE

Future version:

```text
User:
"What are the three most important changes?"

System:
1. Change #14 — ...
   Evidence: Page X → Page Y

2. Change #22 — ...
   Evidence: Page X → Page Y

3. Change #31 — ...
   Evidence: Page X → Page Y
```

The system should NEVER answer from model memory.

It should retrieve from the structured change database.

---

# 35. TABLE COMPARISON ENGINE

Tables require dedicated processing.

Detect:

- added rows,
- removed rows,
- changed cells,
- changed percentages,
- changed thresholds,
- changed column definitions.

Example:

```text
OLD TABLE                 NEW TABLE

Threshold: ₹5L            Threshold: ₹10L
Period: 30 days           Period: 15 days
```

Output:

```text
2 table-level substantive changes detected.
```

---

# 36. OCR QUALITY ENGINE

If a scanned PDF is detected:

```text
Text Extraction
      ↓
Quality Score
      ↓
If Poor
      ↓
OCR
      ↓
OCR Confidence
      ↓
Flag uncertain regions
```

The system should not silently trust poor OCR.

---

# 37. DOCUMENT QUALITY SCORE

Before comparison:

```text
Old Document Quality: 96%
New Document Quality: 91%
```

Factors:

- extractable text,
- OCR confidence,
- missing pages,
- malformed tables,
- corrupted characters,
- heading detection confidence.

This protects the comparison engine from garbage input.

---

# 38. FALSE POSITIVE CONTROL

The system should actively detect:

```text
Page number differences
Header differences
Footer differences
Formatting differences
Whitespace differences
Capitalization changes
Hyphenation differences
```

and classify them as:

```text
NON-SUBSTANTIVE
```

This is essential for user trust.

---

# 39. FALSE NEGATIVE CONTROL

Run multiple comparison strategies:

```text
Structural
+
Lexical
+
Semantic
+
Numerical
+
Obligation
+
Table
+
Cross-reference
```

A change detected by one layer but missed by another should enter a verification queue.

---

# 40. CHANGE CONSENSUS ENGINE

For each potential change:

```text
Structural Matcher → Match
Embedding Matcher → Match
Lexical Matcher → Match
Numerical Engine → Difference
LLM → Substantive Change
```

Then:

```text
Consensus = HIGH
```

This is significantly safer than trusting one model.

---

# 41. ARCHITECTURE

Use a modular architecture:

```text
                  ┌─────────────────────┐
                  │    Web Dashboard    │
                  │       Next.js       │
                  └──────────┬──────────┘
                             │
                         REST / WSS
                             │
                  ┌──────────▼──────────┐
                  │     API Gateway     │
                  │ Node.js / Express   │
                  └──────────┬──────────┘
                             │
                    Analysis Job Queue
                             │
                  ┌──────────▼──────────┐
                  │ Comparison Engine   │
                  │      Python         │
                  └──────────┬──────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
     PDF Parser        Embedding Engine    Rule Engine
          │                  │                  │
          ▼                  ▼                  ▼
      OCR Engine          Vector DB        Numeric Parser
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                     Candidate Changes
                             │
                             ▼
                      Llama 3.2 8B
                             │
                             ▼
                    Change Classifier
                             │
                             ▼
                    Evidence Validator
                             │
                             ▼
                    Change Database
                             │
                             ▼
                      Web Dashboard
```

---

# 42. LOCAL-FIRST AI ARCHITECTURE

Because Llama 3.2 8B is already running locally, the system should prioritize:

```text
PDF
 ↓
Local Processing
 ↓
Local Embeddings
 ↓
Local Llama
 ↓
Local Database
```

No regulatory document should be sent to an external LLM unless explicitly enabled.

This is especially important for sensitive regulatory/compliance workflows.

---

# 43. DATABASE DESIGN

Use PostgreSQL for structured metadata:

```text
documents
document_versions
users
analysis_jobs
change_records
review_records
```

Use MongoDB if flexible document structures are needed:

```text
raw_documents
parsed_sections
llm_outputs
comparison_context
```

Use Qdrant or another vector database for:

```text
clause embeddings
section embeddings
historical requirements
cross-document semantic relationships
```

For a single-user EOD prototype, however, do NOT over-engineer this.

SQLite/PostgreSQL + local vector storage can be sufficient.

The architecture should be scalable without making the MVP unnecessarily complex.

---

# 44. CORE API

Required endpoints:

```text
POST /api/v1/documents/upload

POST /api/v1/comparisons

GET /api/v1/comparisons/{id}

GET /api/v1/comparisons/{id}/changes

GET /api/v1/comparisons/{id}/changes/{change_id}

GET /api/v1/comparisons/{id}/summary

GET /api/v1/comparisons/{id}/statistics

POST /api/v1/changes/{change_id}/review

GET /api/v1/documents/{id}/sections
```

Future:

```text
POST /api/v1/query
GET /api/v1/regulatory-lineage/{circular_id}
GET /api/v1/requirements/{requirement_id}
```

---

# 45. ASYNCHRONOUS PROCESSING

The analysis pipeline should be asynchronous.

```text
Upload
 ↓
Job Created
 ↓
Text Extraction
 ↓
Structural Parsing
 ↓
Clause Alignment
 ↓
Difference Detection
 ↓
LLM Verification
 ↓
Impact Analysis
 ↓
Completed
```

WebSocket/SSE events:

```text
DOCUMENT_UPLOADED
EXTRACTION_STARTED
EXTRACTION_COMPLETED
STRUCTURE_DETECTED
ALIGNMENT_STARTED
DIFFERENCES_DETECTED
AI_CLASSIFICATION_STARTED
VALIDATION_STARTED
ANALYSIS_COMPLETED
```

The user should see real-time progress.

---

# 46. SCORING SYSTEM

Do NOT create one meaningless "AI score."

Instead create measurable system metrics:

### Comparison Confidence

How confident the system is that the detected change is real.

### Semantic Match Confidence

How confident the system is that two clauses correspond.

### Classification Confidence

How confident the system is in the category.

### Evidence Quality

How strong the source evidence is.

### Impact Level

How operationally important the change is.

This is more defensible than pretending a regulatory document can be summarized by one arbitrary score.

---

# 47. EXPLAINABILITY

Every change must answer:

```text
WHAT changed?
WHY is it considered a change?
WHERE did it change?
HOW confident is the system?
WHAT category does it belong to?
WHAT could be the practical implication?
```

Example:

```text
WHAT:
Reporting deadline reduced from 30 to 15 days.

WHERE:
Old: Page 24, Section 4.2
New: Page 31, Section 5.1

CATEGORY:
Timeline Change

IMPACT:
High

CONFIDENCE:
96%

EVIDENCE:
[Old text]
[New text]
```

---

# 48. AUDIT TRAIL

Every AI decision must be traceable.

Store:

```text
comparison_id
model_version
prompt_version
embedding_model
timestamp
source_clause_ids
LLM_output
rule_engine_output
final_classification
reviewer_decision
```

This allows the result to be reproduced.

---

# 49. PROMPT VERSIONING

Do not hard-code prompts.

Create:

```text
/prompts
    change_classifier_v1.txt
    impact_analyzer_v1.txt
    obligation_analyzer_v1.txt
    summarizer_v1.txt
```

Every AI result records the prompt version used.

---

# 50. MODEL EVALUATION

Create a benchmark dataset.

Manually label:

```text
Old Clause
New Clause
Expected Change Type
Expected Category
Expected Impact
```

Then measure:

```text
Precision
Recall
F1 Score
False Positive Rate
False Negative Rate
Classification Accuracy
```

The most important metric should be:

**Substantive Change Recall**

because missing an important regulatory change can be more dangerous than reporting a few extra candidates for human review.

---

# 51. GOLDEN TEST CASES

Create test cases for:

1. Identical documents
2. Completely different documents
3. One added clause
4. One deleted clause
5. Numerical change
6. Deadline change
7. Percentage change
8. Renumbered section
9. Moved paragraph
10. Reworded paragraph
11. One-to-many split
12. Many-to-one merge
13. Table modification
14. Obligation strengthening
15. Obligation relaxation
16. Exception addition
17. Exception removal
18. OCR corruption
19. Header/footer noise
20. Cross-reference modification

---

# 52. SECURITY

Required:

- local processing by default,
- encrypted storage,
- access control,
- secure file handling,
- file-type validation,
- maximum upload size,
- malware scanning where applicable,
- temporary file cleanup,
- audit logs.

Never execute uploaded files.

Treat uploaded PDFs as untrusted input.

---

# 53. PROMPT INJECTION DEFENSE

Regulatory PDFs can contain arbitrary text.

The system must assume document text is **data**, not instructions.

If the document contains:

```text
Ignore previous instructions...
```

Llama must treat this as quoted document content.

System instruction hierarchy:

```text
SYSTEM INSTRUCTIONS
        ↓
APPLICATION INSTRUCTIONS
        ↓
DOCUMENT CONTENT
```

Document content MUST NEVER override system instructions.

---

# 54. RESILIENCE

If Llama fails:

```text
LLM failure
   ↓
Deterministic comparison result preserved
   ↓
Change marked:
"AI interpretation unavailable"
```

The entire system must not collapse because the LLM is unavailable.

This is a crucial architectural principle.

---

# 55. GRACEFUL DEGRADATION

If embeddings fail:

```text
Use lexical + structural matching
```

If OCR fails:

```text
Flag pages requiring manual review
```

If Llama fails:

```text
Return detected textual differences
```

If a document is malformed:

```text
Stop affected section
Continue remaining pages
Report partial-analysis status
```

---

# 56. FUTURISTIC FEATURE 1 — REGULATORY MEMORY

Build a long-term regulatory knowledge base.

Instead of:

```text
Compare PDF A vs PDF B
```

eventually become:

```text
Regulatory Knowledge Graph

Requirement
   ↓
Introduced
   ↓
Modified
   ↓
Clarified
   ↓
Superseded
   ↓
Current Status
```

This solves the real-world problem of losing regulatory history across dozens of circulars.

---

# 57. FUTURISTIC FEATURE 2 — REGULATORY CHANGE IMPACT MAP

Map changes to organizational functions:

```text
Regulatory Change
       │
       ├── Compliance
       ├── Operations
       ├── Technology
       ├── Finance
       ├── Risk
       └── Legal
```

This answers:

> "Who inside my organization needs to care about this?"

---

# 58. FUTURISTIC FEATURE 3 — ACTIONABLE COMPLIANCE WORKFLOW

Convert:

```text
Regulation Change
```

into:

```text
Task
Owner
Priority
Deadline
Evidence
Status
```

Example:

```text
Task:
Update regulatory reporting workflow

Priority:
High

Suggested Owner:
Compliance Reporting Team

Source:
Circular X, Section Y

Status:
Pending Review
```

Do not automatically assign legal obligations without human validation.

---

# 59. FUTURISTIC FEATURE 4 — REGULATORY COPILOT

Users can ask:

```text
"What changed?"

"What became stricter?"

"What was removed?"

"Which changes affect reporting?"

"Show all deadline changes."

"Explain change #17."

"Show changes introduced after version 2."

"What should I review first?"
```

Every answer must contain evidence links.

---

# 60. FUTURISTIC FEATURE 5 — CONTINUOUS REGULATORY MONITORING

Future architecture:

```text
Official Regulatory Sources
          ↓
Document Detector
          ↓
New Circular Detected
          ↓
Download
          ↓
Version Identification
          ↓
Compare Against Current Version
          ↓
Change Detection
          ↓
Impact Analysis
          ↓
Alert
```

Users could receive:

```text
HIGH-IMPACT REGULATORY CHANGE DETECTED
```

instead of manually checking websites every day.

---

# 61. FUTURISTIC FEATURE 6 — REGULATORY ALERTS

Allow alerts based on:

```text
Category
Impact
Institution Type
Topic
Deadline
```

Example:

```text
Alert me whenever a new RBI circular introduces
a reporting deadline change.
```

This directly addresses the operational problem of missing important regulatory updates.

---

# 62. FUTURISTIC FEATURE 7 — CHANGE PREDICTION

Once sufficient historical data exists:

```text
Historical Circulars
        ↓
Regulatory Evolution
        ↓
Pattern Detection
        ↓
Potential Areas of Future Change
```

This should NEVER claim to predict RBI decisions with certainty.

Instead:

> "Historical trend indicates this requirement has been modified repeatedly."

This is regulatory trend intelligence, not regulatory prediction.

---

# 63. FUTURISTIC FEATURE 8 — REQUIREMENT LIFECYCLE

Every requirement gets:

```text
Created
Modified
Clarified
Expanded
Restricted
Suspended
Superseded
Removed
```

This provides a complete lifecycle view.

---

# 64. FUTURISTIC FEATURE 9 — CHANGE CLUSTERING

Group related changes:

```text
Cluster A:
Reporting changes

Cluster B:
Eligibility changes

Cluster C:
Compliance changes

Cluster D:
Threshold changes
```

Then identify:

> "This circular contains a major reporting reform."

The cluster-level summary must be generated from the underlying verified changes.

---

# 65. FUTURISTIC FEATURE 10 — REGULATORY DIFFERENCE API

Expose the comparison engine through an API.

Example:

```http
POST /api/v2/regulatory/compare
```

Input:

```json
{
  "old_document": "...",
  "new_document": "...",
  "analysis_mode": "full"
}
```

Output:

```json
{
  "total_changes": 47,
  "substantive_changes": 31,
  "high_impact_changes": 9,
  "changes": [...]
}
```

This allows other compliance systems to consume the intelligence.

---

# 66. FUTURISTIC FEATURE 11 — MULTI-DOCUMENT COMPARISON

Move beyond two documents:

```text
Circular A
Circular B
Circular C
Circular D
```

and answer:

> "How has this requirement evolved over the last four versions?"

This is significantly more valuable than pairwise comparison.

---

# 67. FUTURISTIC FEATURE 12 — REGULATORY KNOWLEDGE GRAPH

Nodes:

```text
Circular
Section
Clause
Requirement
Entity
Deadline
Threshold
Exception
Referenced Regulation
```

Edges:

```text
contains
modifies
supersedes
references
applies_to
introduced_by
removed_by
```

This eventually turns RegChange AI into a regulatory intelligence platform rather than a document utility.

---

# 68. UI INFORMATION ARCHITECTURE

Main navigation:

```text
Dashboard
│
├── New Comparison
├── Comparisons
├── Change Explorer
├── High-Impact Changes
├── Requirements
├── Regulatory Timeline
├── Knowledge Graph
├── Search / Ask AI
└── Review Queue
```

Comparison page:

```text
Overview
Changes
Added
Removed
Modified
Tables
Impact
Timeline
Evidence
Review
```

---

# 69. MVP PRIORITY

## P0 — MUST WORK

```text
PDF Upload
Text Extraction
OCR Fallback
Document Structure Detection
Clause Segmentation
Old/New Alignment
Added Detection
Removed Detection
Modified Detection
Semantic Matching
Numerical Difference Detection
Change Categorization
Llama 3.2 8B Explanation
Confidence
Page/Section References
Side-by-Side Evidence
Change Dashboard
JSON Export/API
```

## P1 — HIGH VALUE

```text
Impact Scoring
Human Review
Table Comparison
Obligation Strength Analysis
Cross-Reference Detection
Regulatory Summary
Search
Change Filtering
Audit Trail
Model/Prompt Versioning
```

## P2 — FUTURE

```text
Regulatory Knowledge Graph
Version History
Continuous Monitoring
Alerts
Requirement Lifecycle
Role-Based Impact
Action Tracking
Multi-Document Comparison
Regulatory Copilot
Regulatory API
```

---

# 70. DEVELOPMENT PRINCIPLE

Do NOT build all futuristic features before proving the baseline.

Development order:

```text
PHASE 1
Reliable PDF extraction
        ↓
PHASE 2
Structural parsing
        ↓
PHASE 3
Clause alignment
        ↓
PHASE 4
Deterministic difference detection
        ↓
PHASE 5
Semantic matching
        ↓
PHASE 6
Llama classification
        ↓
PHASE 7
Evidence-backed dashboard
        ↓
PHASE 8
Impact analysis
        ↓
PHASE 9
Human review
        ↓
PHASE 10
Regulatory intelligence features
```

---

# 71. SUCCESS CRITERIA

The MVP is successful only if:

### Accuracy

Important substantive changes are consistently detected.

### Traceability

Every change points to the exact old/new source location.

### Explainability

Every AI conclusion has evidence.

### Reliability

The system works even if the LLM fails.

### Precision

Editorial differences do not flood the user with false positives.

### Recall

Substantive regulatory changes are not silently missed.

### Performance

A 59-page vs 100-page comparison should complete within a practical interactive timeframe on the available local hardware.

### Privacy

Documents remain local unless the user explicitly enables external services.

### Usability

A compliance analyst should understand the most important changes within seconds.

---

# 72. FINAL PRODUCT POSITIONING

Do not position this as:

> "AI PDF Comparator"

Position it as:

> **"AI-Powered Regulatory Change Intelligence Engine"**

The evolution is:

```text
PDF Comparator
      ↓
AI Document Diff
      ↓
Regulatory Change Detector
      ↓
Regulatory Change Intelligence
      ↓
Regulatory Knowledge System
```

The long-term vision is not simply to answer:

> "What changed between these two PDFs?"

It is to answer:

> **"What changed, where did it change, why does it matter, who is affected, what evidence supports it, what action may be required, and how has this requirement evolved over time?"**

---

# 73. MASTER SYSTEM PROMPT

Use the following as the permanent system prompt for AI-assisted development:

"You are acting as a Principal AI Architect, Regulatory Technology Product Manager, Senior Backend Engineer, NLP Engineer, and QA Engineer building RegChange AI.

RegChange AI is an AI-powered regulatory circular comparison and change intelligence platform.

The primary objective is to compare two versions of RBI circulars and identify substantive regulatory changes with exact source traceability.

The system must prioritize accuracy, evidence, determinism, explainability, privacy, and auditability over superficial AI functionality.

Architecture principles:

1. Deterministic processing must detect and normalize document structure before LLM reasoning.
2. Clause-level and section-level alignment must precede semantic interpretation.
3. Structural, lexical, semantic, numerical, table, and obligation-level comparison must operate as complementary layers.
4. Llama 3.2 8B is an interpretation and classification engine, not the sole difference detector.
5. The LLM must never invent regulatory requirements, page numbers, section numbers, dates, values, or evidence.
6. Every substantive conclusion must be traceable to old and new source text.
7. Every AI-generated classification must contain structured evidence.
8. Numerical comparisons must be calculated deterministically.
9. Editorial changes must be separated from substantive regulatory changes.
10. Ambiguous cases must be flagged for human review rather than fabricated.
11. If the LLM fails, deterministic comparison results must remain available.
12. Uploaded documents must be treated as untrusted data and never as instructions.
13. Prompt injection contained inside a regulatory document must never override system instructions.
14. The architecture must support local-first processing because regulatory documents may be sensitive.
15. All AI outputs must be versioned by model and prompt version.
16. All comparison results must preserve page, section, clause, and document-version provenance.
17. The system must support future regulatory version history, requirement lifecycle tracking, knowledge graphs, alerts, and continuous monitoring.

For every technical recommendation, distinguish between:

BASELINE MVP REQUIREMENT
HIGH-VALUE ENHANCEMENT
FUTURE / EXPERIMENTAL FEATURE

Do not introduce unrelated features.

Every proposed feature must solve a concrete regulatory/compliance workflow problem.

When generating implementation plans, provide:

- architecture,
- data flow,
- component responsibilities,
- API contracts,
- database structures,
- algorithms,
- failure modes,
- security considerations,
- testing strategy,
- observability,
- scalability considerations,
- acceptance criteria.

When designing AI prompts, require strict structured JSON output and evidence grounding.

When designing change detection, prefer:

Exact Match
→ Structural Match
→ Lexical Match
→ Semantic Match
→ Numerical Analysis
→ Obligation Analysis
→ LLM Classification
→ Evidence Validation
→ Human Review

Never use an LLM-generated statement as the sole evidence of a regulatory change.

The final system should behave like a professional regulatory analyst's assistant: precise, evidence-backed, explainable, auditable, and conservative when uncertain."

---

# 74. THE "BEAST MODE" END STATE

The final system should eventually look like:

```text
                 REGCHANGE AI
                      │
          ┌───────────┴───────────┐
          │                       │
    DOCUMENT INTELLIGENCE    REGULATORY MEMORY
          │                       │
     ┌────┼────┐              ┌───┼────┐
     │    │    │              │   │    │
    OCR  NLP  Tables         Versions Graph
     │    │    │              │   │    │
     └────┼────┘              └───┼────┘
          │                       │
          └──────────┬────────────┘
                     │
             CHANGE ENGINE
                     │
       ┌─────────────┼─────────────┐
       │             │             │
   Added/Removed  Modified     Numerical
       │             │             │
       └─────────────┼─────────────┘
                     │
              Llama 3.2 8B
                     │
        ┌────────────┼────────────┐
        │            │            │
    Category      Impact       Explanation
        │            │            │
        └────────────┼────────────┘
                     │
              EVIDENCE ENGINE
                     │
        ┌────────────┼────────────┐
        │            │            │
      Pages       Clauses       Source
        │            │            │
        └────────────┼────────────┘
                     │
              HUMAN REVIEW
                     │
                     ▼
          REGULATORY INTELLIGENCE
                     │
        ┌────────────┼────────────┐
        │            │            │
      Search       Alerts       Actions
        │            │            │
        └────────────┼────────────┘
                     │
                     ▼
            COMPLIANCE TEAMS
```

**The killer feature is not "we used Llama."**

The killer feature is:

> **A reviewer can open one change, see the exact old clause and new clause side-by-side, understand what changed, see why the AI classified it that way, see the numerical/semantic evidence, verify the confidence, and approve or reject the finding.**

That is what makes this credible in a real regulatory workflow rather than looking like another AI wrapper.