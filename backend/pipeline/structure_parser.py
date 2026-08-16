"""
RegChange AI — Hierarchical Document Structure Parser
Builds a tree representation from extracted PDF content.
Detects chapters, sections, clauses, paragraphs in RBI circulars.
"""
import re
import uuid
import logging
from typing import Optional
from backend.models.document import (
    DocumentNode, ParsedDocument, DocumentMetadata,
    ContentType, DocumentVersion
)
from backend.pipeline.normalizer import TextNormalizer

logger = logging.getLogger(__name__)


class StructureParser:
    """Parse extracted PDF content into hierarchical document model."""
    
    # Font size thresholds (relative to body text)
    HEADING_SIZE_RATIO = 1.15  # 15% larger than average = heading
    
    # RBI-specific patterns
    CHAPTER_RE = re.compile(
        r'^(?:CHAPTER|Chapter)\s*[-–]?\s*([IVXLCDM]+|\d+)\b',
        re.IGNORECASE
    )
    
    SECTION_NUM_RE = re.compile(
        r'^(\d+)\.\s+(.*)',
        re.DOTALL
    )
    
    SUBSECTION_NUM_RE = re.compile(
        r'^(\d+\.\d+)\s+(.*)',
        re.DOTALL
    )
    
    SUB_SUBSECTION_RE = re.compile(
        r'^(\d+\.\d+\.\d+)\s+(.*)',
        re.DOTALL
    )
    
    CLAUSE_LETTER_RE = re.compile(
        r'^\(([a-z])\)\s+(.*)',
        re.DOTALL
    )
    
    CLAUSE_ROMAN_RE = re.compile(
        r'^\(([ivxlcdm]+)\)\s+(.*)',
        re.DOTALL
    )
    
    CLAUSE_NUM_RE = re.compile(
        r'^\((\d+)\)\s+(.*)',
        re.DOTALL
    )
    
    ANNEXURE_RE = re.compile(
        r'^(?:ANNEXURE|Annexure|ANNEX|Appendix|APPENDIX|Schedule|SCHEDULE)\s*(.*)',
        re.IGNORECASE
    )
    
    PART_RE = re.compile(
        r'^(?:PART|Part)\s*[-–]?\s*([IVXLCDM]+|\d+)\b\s*[-–:]?\s*(.*)',
        re.IGNORECASE
    )
    
    DEFINITION_RE = re.compile(
        r'^["\']([^"\']+)["\']?\s+(?:means|refers to|shall mean|includes)',
        re.IGNORECASE
    )
    
    def __init__(self):
        self.normalizer = TextNormalizer()
    
    def parse(self, extracted_data: dict, version: DocumentVersion,
              document_id: Optional[str] = None) -> ParsedDocument:
        """
        Parse extracted PDF data into a hierarchical document model.
        
        Args:
            extracted_data: Output from PDFExtractor.extract()
            version: OLD or NEW
            document_id: Optional ID, auto-generated if not provided
        
        Returns:
            ParsedDocument with hierarchical nodes
        """
        if not document_id:
            document_id = f"DOC_{version.value}_{uuid.uuid4().hex[:8]}"
        
        metadata = DocumentMetadata(
            document_id=document_id,
            filename=extracted_data["filename"],
            total_pages=extracted_data["total_pages"],
            version=version,
            quality_score=extracted_data["quality_score"],
        )
        
        # Extract metadata from first page
        first_page_text = extracted_data["pages"][0]["text"] if extracted_data["pages"] else ""
        self._extract_doc_metadata(first_page_text, metadata)
        
        # Determine average body font size for heading detection
        all_font_sizes = []
        for page in extracted_data["pages"]:
            for block in page.get("blocks", []):
                if block.get("font_size", 0) > 0 and len(block.get("text", "").strip()) > 20:
                    all_font_sizes.append(block["font_size"])
        
        avg_font_size = sum(all_font_sizes) / len(all_font_sizes) if all_font_sizes else 12.0
        
        # Build nodes from all pages
        nodes = []
        current_chapter = None
        current_section = None
        current_subsection = None
        current_part = None
        node_order = 0
        
        # Detect TOC pages (pages with many dot-leader lines)
        toc_pages = set()
        for page_data in extracted_data["pages"]:
            page_text = page_data.get("text", "")
            dot_leader_count = len(re.findall(r'\.{4,}', page_text))
            if dot_leader_count >= 3:
                toc_pages.add(page_data["page_number"])
        
        if toc_pages:
            logger.info(f"Detected TOC pages: {sorted(toc_pages)}")
        
        # Track seen chapter numbers to avoid duplicates from TOC
        seen_chapters = set()
        
        for page_data in extracted_data["pages"]:
            page_num = page_data["page_number"]
            is_toc_page = page_num in toc_pages
            
            # Process text blocks
            for block in page_data.get("blocks", []):
                text = block["text"].strip()
                if not text or len(text) < 3:
                    continue
                
                # Skip very short standalone numbers (page numbers)
                if re.match(r'^\d{1,3}$', text):
                    continue
                
                # Skip TOC entries (lines with dot leaders like "CHAPTER I ........... 4")
                if re.search(r'\.{4,}', text):
                    continue
                
                # Skip "Contents" header
                if re.match(r'^\s*Contents\s*$', text, re.IGNORECASE):
                    continue
                
                # Skip blocks that are just page references (common in TOC)
                if is_toc_page and re.match(r'^[A-Z][a-z]+.*\d+\s*$', text.split('\n')[0]):
                    # Looks like a TOC entry without dots
                    if len(text.strip()) < 100:
                        continue
                
                font_size = block.get("font_size", 12.0)
                is_bold = block.get("is_bold", False)
                is_heading = (font_size > avg_font_size * self.HEADING_SIZE_RATIO) or is_bold
                
                # Determine content type and hierarchy
                node_type, section_num, heading_text, body_text = self._classify_block(
                    text, is_heading, font_size, avg_font_size
                )
                
                node_id = f"{document_id}_N{len(nodes):04d}"
                
                # Determine parent
                parent_id = None
                depth = 0
                
                if node_type == ContentType.CHAPTER:
                    current_chapter = node_id
                    current_section = None
                    current_subsection = None
                    current_part = None
                    depth = 1
                    
                elif node_type == ContentType.ANNEXURE:
                    current_chapter = node_id
                    current_section = None
                    current_subsection = None
                    current_part = None
                    depth = 1
                    
                elif node_type == ContentType.SECTION:
                    parent_id = current_part or current_chapter
                    current_section = node_id
                    current_subsection = None
                    depth = 3 if current_part else 2
                    
                elif node_type == ContentType.SUBSECTION:
                    parent_id = current_section or current_part or current_chapter
                    current_subsection = node_id
                    depth = 4 if current_part else 3
                    
                elif node_type in (ContentType.CLAUSE, ContentType.SUB_CLAUSE):
                    parent_id = current_subsection or current_section or current_part or current_chapter
                    depth = 5 if current_subsection else (4 if current_section else 3)
                    
                elif node_type == ContentType.PARAGRAPH:
                    parent_id = current_subsection or current_section or current_part or current_chapter
                    depth = 5 if current_subsection else (4 if current_section else 3)
                
                # Handle PART as intermediate level
                if node_type == ContentType.SECTION:
                    part_match = self.PART_RE.match(text)
                    if part_match and is_heading:
                        node_type = ContentType.SECTION  # treat as section-level
                        parent_id = current_chapter
                        current_part = node_id
                        current_section = None
                        current_subsection = None
                        depth = 2
                
                normalized = self.normalizer.normalize(text)
                normalized_for_cmp = self.normalizer.normalize_for_comparison(text)
                
                node = DocumentNode(
                    node_id=node_id,
                    document_id=document_id,
                    document_version=version,
                    page_start=page_num,
                    page_end=page_num,
                    section_number=section_num,
                    heading=heading_text,
                    parent_id=parent_id,
                    text=normalized,
                    normalized_text=normalized_for_cmp,
                    raw_text=text,
                    content_type=node_type,
                    depth=depth,
                    order=node_order,
                    font_info={
                        "size": font_size,
                        "is_bold": is_bold,
                        "name": block.get("font_name", ""),
                    },
                )
                
                # Add as child of parent
                if parent_id:
                    for existing in nodes:
                        if existing.node_id == parent_id:
                            existing.children_ids.append(node_id)
                            break
                
                nodes.append(node)
                node_order += 1
            
            # Process tables
            for table_idx, table in enumerate(page_data.get("tables", [])):
                node_id = f"{document_id}_T{page_num:03d}_{table_idx}"
                parent_id = current_subsection or current_section or current_chapter
                
                table_text = self._table_to_text(table)
                
                node = DocumentNode(
                    node_id=node_id,
                    document_id=document_id,
                    document_version=version,
                    page_start=page_num,
                    page_end=page_num,
                    parent_id=parent_id,
                    text=table_text,
                    normalized_text=self.normalizer.normalize_for_comparison(table_text),
                    raw_text=table_text,
                    content_type=ContentType.TABLE,
                    depth=4,
                    order=node_order,
                    table_data=table,
                )
                
                if parent_id:
                    for existing in nodes:
                        if existing.node_id == parent_id:
                            existing.children_ids.append(node_id)
                            break
                
                nodes.append(node)
                node_order += 1
        
        # Merge consecutive paragraph nodes that belong together
        nodes = self._merge_split_paragraphs(nodes)
        
        # Identify root nodes
        root_ids = [n.node_id for n in nodes if n.parent_id is None]
        
        doc = ParsedDocument(
            metadata=metadata,
            nodes=nodes,
            root_ids=root_ids,
        )
        
        logger.info(
            f"Parsed {len(nodes)} nodes from {metadata.filename}, "
            f"{len(root_ids)} root nodes, "
            f"{len(doc.get_clauses())} comparison units"
        )
        
        return doc
    
    def _classify_block(self, text: str, is_heading: bool,
                        font_size: float, avg_font_size: float
                        ) -> tuple[ContentType, str, str, str]:
        """
        Classify a text block into content type.
        Returns: (content_type, section_number, heading_text, body_text)
        """
        first_line = text.split('\n')[0].strip()
        
        # Check for chapter
        chapter_match = self.CHAPTER_RE.match(first_line)
        if chapter_match:
            chapter_num = chapter_match.group(1)
            heading = text[chapter_match.end():].strip().split('\n')[0].strip()
            return ContentType.CHAPTER, f"Ch.{chapter_num}", heading, text
        
        # Check for annexure
        annexure_match = self.ANNEXURE_RE.match(first_line)
        if annexure_match:
            heading = annexure_match.group(1).strip()
            return ContentType.ANNEXURE, f"Annexure {heading}", heading, text
        
        # Check for Part
        part_match = self.PART_RE.match(first_line)
        if part_match and is_heading:
            part_num = part_match.group(1)
            heading = part_match.group(2).strip()
            return ContentType.SECTION, f"Part {part_num}", heading, text
        
        # Check for sub-subsection (1.1.1)
        sub_sub_match = self.SUB_SUBSECTION_RE.match(first_line)
        if sub_sub_match:
            sec_num = sub_sub_match.group(1)
            rest = sub_sub_match.group(2).strip()
            heading = rest.split('\n')[0].strip() if is_heading else ""
            return ContentType.SUBSECTION, sec_num, heading, text
        
        # Check for subsection (1.1)
        subsec_match = self.SUBSECTION_NUM_RE.match(first_line)
        if subsec_match:
            sec_num = subsec_match.group(1)
            rest = subsec_match.group(2).strip()
            heading = rest.split('\n')[0].strip()[:80] if is_heading else ""
            return ContentType.SUBSECTION, sec_num, heading, text
        
        # Check for section (1.)
        sec_match = self.SECTION_NUM_RE.match(first_line)
        if sec_match:
            sec_num = sec_match.group(1)
            rest = sec_match.group(2).strip()
            heading = rest.split('\n')[0].strip()[:80] if is_heading else ""
            # If short text with bold, it's a section heading
            if is_heading and len(first_line) < 120:
                return ContentType.SECTION, sec_num, heading, text
            else:
                return ContentType.CLAUSE, sec_num, "", text
        
        # Check for lettered clause (a)
        letter_match = self.CLAUSE_LETTER_RE.match(first_line)
        if letter_match:
            clause_id = f"({letter_match.group(1)})"
            return ContentType.CLAUSE, clause_id, "", text
        
        # Check for roman numeral clause (i)
        roman_match = self.CLAUSE_ROMAN_RE.match(first_line)
        if roman_match:
            clause_id = f"({roman_match.group(1)})"
            return ContentType.SUB_CLAUSE, clause_id, "", text
        
        # Check for numbered clause (1)
        num_clause_match = self.CLAUSE_NUM_RE.match(first_line)
        if num_clause_match:
            clause_id = f"({num_clause_match.group(1)})"
            return ContentType.SUB_CLAUSE, clause_id, "", text
        
        # Check for definition
        if self.DEFINITION_RE.match(text):
            return ContentType.DEFINITION, "", "", text
        
        # Bold heading without numbering
        if is_heading and len(first_line) < 100 and font_size > avg_font_size * 1.1:
            return ContentType.SECTION, "", first_line, text
        
        # Default: paragraph
        return ContentType.PARAGRAPH, "", "", text
    
    def _merge_split_paragraphs(self, nodes: list[DocumentNode]) -> list[DocumentNode]:
        """Merge consecutive paragraph nodes that were split by PDF extraction."""
        if not nodes:
            return nodes
        
        merged = []
        i = 0
        
        while i < len(nodes):
            node = nodes[i]
            
            # Only merge paragraphs
            if node.content_type == ContentType.PARAGRAPH and not node.section_number:
                # Look ahead for continuation paragraphs
                combined_text = node.text
                last_page = node.page_end
                j = i + 1
                
                while j < len(nodes):
                    next_node = nodes[j]
                    # Same parent, same type, consecutive, no section number
                    if (next_node.content_type == ContentType.PARAGRAPH
                            and not next_node.section_number
                            and next_node.parent_id == node.parent_id
                            and next_node.page_start <= last_page + 1
                            and not next_node.heading):
                        
                        # Check if text is a continuation (starts lowercase or with common connectors)
                        first_char = next_node.text.strip()[0] if next_node.text.strip() else ''
                        if first_char.islower() or first_char in ',-;':
                            combined_text += " " + next_node.text
                            last_page = next_node.page_end
                            j += 1
                            continue
                    break
                
                if j > i + 1:
                    # Update the merged node
                    node.text = combined_text
                    node.normalized_text = self.normalizer.normalize_for_comparison(combined_text)
                    node.page_end = last_page
                    i = j
                else:
                    i += 1
                
                merged.append(node)
            else:
                merged.append(node)
                i += 1
        
        return merged
    
    def _table_to_text(self, table: list[list[str]]) -> str:
        """Convert table to text representation."""
        lines = []
        for row in table:
            lines.append(" | ".join(cell for cell in row))
        return "\n".join(lines)
    
    def _extract_doc_metadata(self, first_page_text: str, metadata: DocumentMetadata):
        """Extract metadata from first page text."""
        lines = first_page_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if re.match(r'^RBI/', line):
                metadata.circular_number = line
            elif 'Master Direction' in line:
                metadata.title = line
            elif re.match(r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+', line):
                metadata.issue_date = line
