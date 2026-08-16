"""Quick test of the core RegChange AI pipeline."""
import sys
import os
import time

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.pipeline.pdf_extractor import PDFExtractor
from backend.pipeline.structure_parser import StructureParser
from backend.pipeline.clause_aligner import ClauseAligner, AlignmentType
from backend.pipeline.change_classifier import ChangeClassifier
from backend.pipeline.impact_scorer import ImpactScorer
from backend.pipeline.confidence_engine import ConfidenceEngine
from backend.models.document import DocumentVersion
from backend.models.change import ChangeType

OLD_PDF = "18MDKYCE7A0F2A0494647248DBA377E4B9317E0.PDF"
NEW_PDF = "MD18KYCF6E92C82E1E1419D87323E3869BC9F13.pdf"

start = time.time()

print("=" * 60)
print("  RegChange AI — Pipeline Test")
print("=" * 60)

# Phase 1: Extract
print("\n[1/6] Extracting PDFs...")
extractor = PDFExtractor()
old_data = extractor.extract(OLD_PDF)
new_data = extractor.extract(NEW_PDF)
print(f"  Old: {old_data['total_pages']} pages, quality={old_data['quality_score']:.3f}")
print(f"  New: {new_data['total_pages']} pages, quality={new_data['quality_score']:.3f}")

# Phase 2: Parse structure
print("\n[2/6] Parsing document structure...")
parser = StructureParser()
old_parsed = parser.parse(old_data, DocumentVersion.OLD)
new_parsed = parser.parse(new_data, DocumentVersion.NEW)
print(f"  Old: {len(old_parsed.nodes)} nodes, {len(old_parsed.get_clauses())} clauses, {len(old_parsed.get_sections())} sections")
print(f"  New: {len(new_parsed.nodes)} nodes, {len(new_parsed.get_clauses())} clauses, {len(new_parsed.get_sections())} sections")

# Show some sections
print("\n  Old document sections:")
for s in old_parsed.get_sections()[:8]:
    print(f"    {s.section_number}: {s.heading[:60] if s.heading else '(no heading)'} [p.{s.page_start}]")

print("\n  New document sections:")
for s in new_parsed.get_sections()[:8]:
    print(f"    {s.section_number}: {s.heading[:60] if s.heading else '(no heading)'} [p.{s.page_start}]")

# Phase 3: Align clauses
print("\n[3/6] Aligning clauses (this may take a minute for semantic matching)...")
t_align = time.time()

try:
    aligner = ClauseAligner(use_semantic=True)
except Exception as e:
    print(f"  Semantic matching unavailable ({e}), using lexical only")
    aligner = ClauseAligner(use_semantic=False)

alignments = aligner.align(old_parsed, new_parsed)

added = sum(1 for a in alignments if a.alignment_type == AlignmentType.ADDED)
removed = sum(1 for a in alignments if a.alignment_type == AlignmentType.REMOVED)
matched = len(alignments) - added - removed

print(f"  {len(alignments)} total alignments: {matched} matched, {added} added, {removed} removed")
print(f"  Alignment took {time.time() - t_align:.1f}s")

# Phase 4: Classify changes
print("\n[4/6] Classifying changes...")
classifier = ChangeClassifier()
changes = []
change_counter = 0

for alignment in alignments:
    # Skip unchanged
    if alignment.alignment_type not in (AlignmentType.ADDED, AlignmentType.REMOVED):
        if alignment.old_nodes and alignment.new_nodes:
            if alignment.old_nodes[0].normalized_text == alignment.new_nodes[0].normalized_text:
                continue
    
    change_counter += 1
    change_id = f"CHG-{change_counter:04d}"
    record = classifier.classify_alignment(alignment, change_id, "TEST")
    
    if record.change_type == ChangeType.UNCHANGED:
        change_counter -= 1
        continue
    
    changes.append(record)

print(f"  {len(changes)} changes detected")

# Phase 5: Score impact
print("\n[5/6] Scoring impact...")
scorer = ImpactScorer()
changes = scorer.score_all(changes)

# Phase 6: Confidence
print("\n[6/6] Computing confidence...")
conf_engine = ConfidenceEngine()
changes = conf_engine.compute_all(changes)

elapsed = time.time() - start

# === Results Summary ===
print("\n" + "=" * 60)
print("  RESULTS SUMMARY")
print("=" * 60)

substantive = [c for c in changes if c.is_substantive]
editorial = [c for c in changes if not c.is_substantive]

print(f"\n  Total changes:       {len(changes)}")
print(f"  Substantive:         {len(substantive)}")
print(f"  Editorial:           {len(editorial)}")
print(f"  Added:               {sum(1 for c in changes if c.change_type == ChangeType.ADDED)}")
print(f"  Removed:             {sum(1 for c in changes if c.change_type == ChangeType.REMOVED)}")
print(f"  Modified:            {sum(1 for c in changes if c.change_type == ChangeType.MODIFIED)}")
print(f"  Relocated:           {sum(1 for c in changes if c.change_type == ChangeType.RELOCATED)}")
print(f"  Reworded:            {sum(1 for c in changes if c.change_type == ChangeType.REWORDED)}")

print(f"\n  Impact Distribution:")
from backend.models.change import ImpactLevel
for level in ImpactLevel:
    count = sum(1 for c in changes if c.impact == level)
    print(f"    {level.value:15s}: {count}")

print(f"\n  Category Distribution (substantive only):")
from collections import Counter
from backend.config import CHANGE_CATEGORIES
cat_counts = Counter(c.category.value for c in substantive)
for cat, count in cat_counts.most_common():
    label = CHANGE_CATEGORIES.get(cat, cat)
    print(f"    {label:30s}: {count}")

print(f"\n  Average Confidence: {sum(c.confidence.overall for c in changes) / max(len(changes), 1):.2f}")

# Show top high-impact changes
print("\n  Top 10 High-Impact Substantive Changes:")
high_impact = sorted(substantive, key=lambda c: ['CRITICAL','HIGH','MEDIUM','LOW','INFORMATIONAL'].index(c.impact.value))
for c in high_impact[:10]:
    print(f"    [{c.change_id}] {c.impact.value:12s} | {c.category.value} | {c.change_summary[:80]}")

print(f"\n  Total time: {elapsed:.1f}s")
print("=" * 60)
