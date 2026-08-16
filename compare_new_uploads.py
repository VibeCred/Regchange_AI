"""
RegChange AI — Compare two PDFs from new_uploads/ and export results to CSV.

This script runs the full 6-phase pipeline on the two documents in new_uploads/
and writes all detected regulatory changes to a CSV file.
"""
import sys
import os
import csv
import time
import json

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.pipeline.pdf_extractor import PDFExtractor
from backend.pipeline.normalizer import TextNormalizer
from backend.pipeline.structure_parser import StructureParser
from backend.pipeline.clause_aligner import ClauseAligner, AlignmentType
from backend.pipeline.change_classifier import ChangeClassifier
from backend.pipeline.impact_scorer import ImpactScorer
from backend.pipeline.confidence_engine import ConfidenceEngine
from backend.models.document import DocumentVersion
from backend.models.change import ChangeType, ImpactLevel
from backend.config import CHANGE_CATEGORIES

# === Locate the two PDFs in new_uploads/ ===
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "new_uploads")

files = [f for f in os.listdir(UPLOADS_DIR) if f.lower().endswith('.pdf')]
if len(files) < 2:
    print(f"ERROR: Need at least 2 PDFs in {UPLOADS_DIR}, found {len(files)}")
    sys.exit(1)

# Identify old vs new by examining circular dates from PDF text
import fitz

def _get_circular_year(filepath):
    """Extract the year from the RBI circular reference number."""
    try:
        doc = fitz.open(filepath)
        first_page = doc[0].get_text()[:500]
        doc.close()
        # Look for year patterns like 2023-24, 2025-26
        import re
        year_match = re.search(r'RBI[/\s].*?(\d{4})-\d{2}', first_page)
        if year_match:
            return int(year_match.group(1))
        # Fallback: look for date patterns
        date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+(\d{4})', first_page)
        if date_match:
            return int(date_match.group(2))
    except:
        pass
    return 0

files_with_year = [(f, _get_circular_year(os.path.join(UPLOADS_DIR, f))) for f in files]
files_with_year.sort(key=lambda x: x[1])  # Sort ascending: oldest first

OLD_PDF = os.path.join(UPLOADS_DIR, files_with_year[0][0])
NEW_PDF = os.path.join(UPLOADS_DIR, files_with_year[1][0])

print(f"\n  Document dates detected: {files_with_year[0][0]} ({files_with_year[0][1]}), {files_with_year[1][0]} ({files_with_year[1][1]})")

OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regulatory_changes_output.csv")

start = time.time()

print("=" * 70)
print("  RegChange AI -- New Uploads Comparison")
print("=" * 70)
print(f"\n  Old document: {os.path.basename(OLD_PDF)} ({os.path.getsize(OLD_PDF):,} bytes)")
print(f"  New document: {os.path.basename(NEW_PDF)} ({os.path.getsize(NEW_PDF):,} bytes)")
print(f"  Output CSV:   {OUTPUT_CSV}")

# =============================
# Phase 1: Extract PDFs
# =============================
print("\n[1/6] Extracting PDFs...")
extractor = PDFExtractor()
old_data = extractor.extract(OLD_PDF)
new_data = extractor.extract(NEW_PDF)
print(f"  Old: {old_data['total_pages']} pages, quality={old_data['quality_score']:.3f}")
print(f"  New: {new_data['total_pages']} pages, quality={new_data['quality_score']:.3f}")

# =============================
# Phase 2: Parse structure
# =============================
print("\n[2/6] Parsing document structure...")
parser = StructureParser()
old_parsed = parser.parse(old_data, DocumentVersion.OLD)
new_parsed = parser.parse(new_data, DocumentVersion.NEW)
print(f"  Old: {len(old_parsed.nodes)} nodes, {len(old_parsed.get_clauses())} clauses, {len(old_parsed.get_sections())} sections")
print(f"  New: {len(new_parsed.nodes)} nodes, {len(new_parsed.get_clauses())} clauses, {len(new_parsed.get_sections())} sections")

# Show sections for context
print("\n  Old document sections:")
for s in old_parsed.get_sections()[:10]:
    heading = s.heading[:65] if s.heading else '(no heading)'
    print(f"    {s.section_number or '-'}: {heading} [p.{s.page_start}]")

print("\n  New document sections:")
for s in new_parsed.get_sections()[:10]:
    heading = s.heading[:65] if s.heading else '(no heading)'
    print(f"    {s.section_number or '-'}: {heading} [p.{s.page_start}]")

# =============================
# Phase 3: Align clauses
# =============================
print("\n[3/6] Aligning clauses (semantic matching)...")
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

# =============================
# Phase 4: Classify changes
# =============================
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
    record = classifier.classify_alignment(alignment, change_id, "NEW_UPLOADS")

    if record.change_type == ChangeType.UNCHANGED:
        change_counter -= 1
        continue

    changes.append(record)

print(f"  {len(changes)} changes detected")

# =============================
# Phase 5: Score impact
# =============================
print("\n[5/6] Scoring impact...")
scorer = ImpactScorer()
changes = scorer.score_all(changes)

# =============================
# Phase 6: Confidence
# =============================
print("\n[6/6] Computing confidence...")
conf_engine = ConfidenceEngine()
changes = conf_engine.compute_all(changes)

elapsed = time.time() - start

# =============================
# Results Summary
# =============================
print("\n" + "=" * 70)
print("  RESULTS SUMMARY")
print("=" * 70)

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
for level in ImpactLevel:
    count = sum(1 for c in changes if c.impact == level)
    print(f"    {level.value:15s}: {count}")

print(f"\n  Average Confidence: {sum(c.confidence.overall for c in changes) / max(len(changes), 1):.2f}")

# =============================
# Write CSV Output
# =============================
print(f"\n  Writing CSV to: {OUTPUT_CSV}")

csv_headers = [
    "Change ID",
    "Impact Level",
    "Change Type",
    "Category Code",
    "Category Name",
    "Substantive",
    "Confidence (%)",
    "Change Summary",
    "Old Document Location (Page)",
    "Old Document Section",
    "Old Requirement Text",
    "New Document Location (Page)",
    "New Document Section",
    "New Requirement Text",
    "Numerical Changes",
    "Obligation Analysis",
    "Impact Explanation",
]

with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
    writer.writeheader()

    for c in changes:
        # Extract location info
        old_page = ""
        old_section = ""
        new_page = ""
        new_section = ""

        if c.old_reference:
            old_page = str(c.old_reference.page) if c.old_reference.page else ""
            old_section = c.old_reference.section or c.old_reference.clause or ""
        
        if c.new_reference:
            new_page = str(c.new_reference.page) if c.new_reference.page else ""
            new_section = c.new_reference.section or c.new_reference.clause or ""

        # Numerical changes description
        num_desc_parts = []
        for nc in c.numerical_changes:
            part = f"{nc.field or 'value'}: {nc.old_value} -> {nc.new_value}"
            if nc.direction:
                part += f" ({nc.direction}"
                if nc.magnitude_percent:
                    part += f", {nc.magnitude_percent:.0f}%"
                part += ")"
            num_desc_parts.append(part)
        num_desc = "; ".join(num_desc_parts)

        # Obligation change
        ob_desc = ""
        if c.obligation_change and c.obligation_change.direction and c.obligation_change.direction != "UNCHANGED":
            ob_desc = f"{c.obligation_change.direction}: {c.obligation_change.explanation or ''}"

        cat_code = c.category.value if c.category else ""
        cat_name = CHANGE_CATEGORIES.get(cat_code, cat_code)

        row = {
            "Change ID": c.change_id,
            "Impact Level": c.impact.value if c.impact else "INFORMATIONAL",
            "Change Type": c.change_type.value if c.change_type else "",
            "Category Code": cat_code,
            "Category Name": cat_name,
            "Substantive": "Yes" if c.is_substantive else "No",
            "Confidence (%)": f"{round(c.confidence.overall * 100)}",
            "Change Summary": c.change_summary or "",
            "Old Document Location (Page)": old_page,
            "Old Document Section": old_section,
            "Old Requirement Text": c.old_requirement or "",
            "New Document Location (Page)": new_page,
            "New Document Section": new_section,
            "New Requirement Text": c.new_requirement or "",
            "Numerical Changes": num_desc,
            "Obligation Analysis": ob_desc,
            "Impact Explanation": c.impact_explanation or "",
        }
        writer.writerow(row)

print(f"  CSV written successfully with {len(changes)} rows.")

# Show top 10 changes preview
print("\n  Top 10 High-Impact Changes:")
high_impact = sorted(changes, key=lambda c: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMATIONAL'].index(c.impact.value))
for c in high_impact[:10]:
    summary = (c.change_summary or "")[:85]
    print(f"    [{c.change_id}] {c.impact.value:12s} | {c.category.value} | {summary}")

print(f"\n  Total time: {elapsed:.1f}s")
print("=" * 70)
print(f"\n  OUTPUT FILE: {OUTPUT_CSV}")
print("  Open it in Excel/Google Sheets for full analysis.")
