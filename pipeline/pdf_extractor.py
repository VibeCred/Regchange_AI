"""
RegChange AI — PDF Text Extraction
Extracts text from PDF documents with page-level provenance,
font information for heading detection, and table extraction.
"""
import fitz  # PyMuPDF
import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text and structure from PDF documents."""
    
    def __init__(self):
        self.min_text_quality = 0.3  # minimum ratio of alphanumeric chars
    
    def extract(self, pdf_path: str) -> dict:
        """
        Extract text from a PDF file with full provenance.
        
        Returns:
            {
                "filename": str,
                "total_pages": int,
                "quality_score": float,
                "pages": [
                    {
                        "page_number": int (1-indexed),
                        "text": str,
                        "blocks": [
                            {
                                "text": str,
                                "bbox": (x0, y0, x1, y1),
                                "font_size": float,
                                "is_bold": bool,
                                "font_name": str,
                                "block_type": str  # "text" or "image"
                            }
                        ],
                        "tables": [...],
                        "quality_score": float
                    }
                ]
            }
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        doc = fitz.open(pdf_path)
        result = {
            "filename": os.path.basename(pdf_path),
            "total_pages": len(doc),
            "pages": [],
            "quality_score": 0.0,
        }
        
        page_qualities = []
        
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_data = self._extract_page(page, page_idx + 1)
            result["pages"].append(page_data)
            page_qualities.append(page_data["quality_score"])
        
        # Overall quality
        if page_qualities:
            result["quality_score"] = sum(page_qualities) / len(page_qualities)
        
        doc.close()
        logger.info(
            f"Extracted {result['total_pages']} pages from {result['filename']}, "
            f"quality={result['quality_score']:.2f}"
        )
        return result
    
    def _extract_page(self, page: fitz.Page, page_number: int) -> dict:
        """Extract text and blocks from a single page."""
        page_data = {
            "page_number": page_number,
            "text": "",
            "blocks": [],
            "tables": [],
            "quality_score": 1.0,
        }
        
        # Extract text blocks with font information
        blocks = self._extract_blocks(page)
        page_data["blocks"] = blocks
        
        # Combine text
        page_data["text"] = "\n".join(b["text"] for b in blocks if b["text"].strip())
        
        # Extract tables
        tables = self._extract_tables(page)
        page_data["tables"] = tables
        
        # Calculate quality
        page_data["quality_score"] = self._calculate_quality(page_data["text"])
        
        return page_data
    
    def _extract_blocks(self, page: fitz.Page) -> list[dict]:
        """Extract text blocks with font metadata."""
        blocks = []
        
        # Get detailed text with font info
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # 0 = text block
                continue
            
            block_text_parts = []
            font_sizes = []
            is_bold_parts = []
            font_names = []
            
            for line in block.get("lines", []):
                line_text = ""
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    line_text += span_text
                    
                    font_size = span.get("size", 12.0)
                    font_name = span.get("font", "")
                    is_bold = "Bold" in font_name or "bold" in font_name
                    
                    if span_text.strip():
                        font_sizes.append(font_size)
                        is_bold_parts.append(is_bold)
                        font_names.append(font_name)
                
                block_text_parts.append(line_text)
            
            block_text = "\n".join(block_text_parts)
            
            if not block_text.strip():
                continue
            
            # Determine dominant font properties
            avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12.0
            is_bold = sum(is_bold_parts) > len(is_bold_parts) / 2 if is_bold_parts else False
            dominant_font = max(set(font_names), key=font_names.count) if font_names else ""
            
            blocks.append({
                "text": block_text,
                "bbox": tuple(block.get("bbox", (0, 0, 0, 0))),
                "font_size": round(avg_font_size, 1),
                "is_bold": is_bold,
                "font_name": dominant_font,
                "block_type": "text",
            })
        
        return blocks
    
    def _extract_tables(self, page: fitz.Page) -> list[list[list[str]]]:
        """Extract tables from the page."""
        tables = []
        try:
            found_tables = page.find_tables()
            if found_tables and found_tables.tables:
                for table in found_tables.tables:
                    extracted = table.extract()
                    if extracted:
                        # Clean cell values
                        clean_table = []
                        for row in extracted:
                            clean_row = [
                                (cell.strip() if cell else "") 
                                for cell in row
                            ]
                            if any(clean_row):
                                clean_table.append(clean_row)
                        if clean_table:
                            tables.append(clean_table)
        except Exception as e:
            logger.warning(f"Table extraction failed: {e}")
        
        return tables
    
    def _calculate_quality(self, text: str) -> float:
        """Calculate text extraction quality score."""
        if not text.strip():
            return 0.0
        
        total_chars = len(text)
        if total_chars == 0:
            return 0.0
        
        # Ratio of alphanumeric + common punctuation characters
        good_chars = sum(1 for c in text if c.isalnum() or c in ' .,;:()/-\n\t')
        quality = good_chars / total_chars
        
        # Check for common OCR artifacts
        artifact_patterns = [
            r'[^\x00-\x7F\u0900-\u097F\u20B9]',  # non-ASCII/non-Devanagari chars
        ]
        
        artifact_count = 0
        for pattern in artifact_patterns:
            artifact_count += len(re.findall(pattern, text))
        
        artifact_ratio = artifact_count / total_chars if total_chars > 0 else 0
        quality -= artifact_ratio * 0.5
        
        return max(0.0, min(1.0, quality))
    
    def extract_metadata(self, pdf_path: str) -> dict:
        """Extract document metadata from the first page."""
        doc = fitz.open(pdf_path)
        first_page_text = doc[0].get_text()
        doc.close()
        
        metadata = {
            "circular_number": "",
            "title": "",
            "issue_date": "",
            "update_dates": [],
        }
        
        lines = first_page_text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Circular number (e.g., RBI/DBR/2015-16/18)
            if re.match(r'^RBI/', line):
                metadata["circular_number"] = line
            
            # Direction number
            elif re.match(r'^Master Direction', line, re.IGNORECASE):
                metadata["title"] = line
            
            # Dates
            elif "Updated as on" in line:
                date_match = re.search(r'(\w+ \d+, \d{4})', line)
                if date_match:
                    metadata["update_dates"].append(date_match.group(1))
            
            # Issue date
            elif re.match(r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+', line):
                metadata["issue_date"] = line
        
        return metadata
