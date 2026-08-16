"""
RegChange AI — Text Normalization
Normalizes extracted text while preserving regulatory meaning.
"""
import re
import unicodedata
import logging

logger = logging.getLogger(__name__)


class TextNormalizer:
    """Normalize text for comparison while preserving meaning."""
    
    # Common header/footer patterns in RBI circulars
    HEADER_FOOTER_PATTERNS = [
        r'^\s*\d+\s*$',                    # standalone page numbers
        r'^\s*Page\s+\d+\s+of\s+\d+\s*$',  # Page X of Y
        r'^\s*-\s*\d+\s*-\s*$',            # - N - page indicators
    ]
    
    # Currency normalization
    CURRENCY_MAP = {
        '₹': 'INR ',
        'Rs.': 'INR ',
        'Rs ': 'INR ',
        'Rupees ': 'INR ',
    }
    
    def normalize(self, text: str) -> str:
        """Apply all normalization steps."""
        if not text:
            return ""
        
        text = self._unicode_normalize(text)
        text = self._fix_encoding_artifacts(text)
        text = self._normalize_whitespace(text)
        text = self._fix_hyphenation(text)
        text = self._remove_headers_footers(text)
        text = self._normalize_quotes(text)
        text = self._normalize_dashes(text)
        
        return text.strip()
    
    def normalize_for_comparison(self, text: str) -> str:
        """
        Aggressive normalization for comparison purposes.
        Preserves regulatory meaning but removes formatting noise.
        """
        text = self.normalize(text)
        text = self._normalize_currencies(text)
        text = self._collapse_whitespace(text)
        text = text.lower()
        return text.strip()
    
    def _unicode_normalize(self, text: str) -> str:
        """NFC Unicode normalization."""
        return unicodedata.normalize('NFC', text)
    
    def _fix_encoding_artifacts(self, text: str) -> str:
        """Fix common encoding/OCR artifacts in RBI documents."""
        replacements = {
            '\x92': "'",     # Windows smart quote
            '\x93': '"',     # Windows smart quote
            '\x94': '"',     # Windows smart quote
            '\x96': '-',     # En dash
            '\x97': '-',     # Em dash
            '�': '',         # Replacement character (common in old PDFs)
            '\uf0b7': '•',   # Bullet
            '\uf0a7': '§',   # Section sign
            '\u00a0': ' ',   # Non-breaking space
            '\u2018': "'",   # Left single quote
            '\u2019': "'",   # Right single quote
            '\u201c': '"',   # Left double quote
            '\u201d': '"',   # Right double quote
            '\u2013': '-',   # En dash
            '\u2014': '-',   # Em dash
            '\u2022': '•',   # Bullet
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace and line breaks."""
        # Replace multiple spaces with single space
        text = re.sub(r'[^\S\n]+', ' ', text)
        # Replace multiple blank lines with single blank line
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Remove trailing whitespace on each line
        lines = [line.rstrip() for line in text.split('\n')]
        return '\n'.join(lines)
    
    def _fix_hyphenation(self, text: str) -> str:
        """Fix word-break hyphenation from PDF extraction."""
        # Join hyphenated words at line breaks
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
        return text
    
    def _remove_headers_footers(self, text: str) -> str:
        """Remove common headers and footers."""
        lines = text.split('\n')
        clean_lines = []
        
        for line in lines:
            is_hf = False
            for pattern in self.HEADER_FOOTER_PATTERNS:
                if re.match(pattern, line, re.IGNORECASE):
                    is_hf = True
                    break
            if not is_hf:
                clean_lines.append(line)
        
        return '\n'.join(clean_lines)
    
    def _normalize_quotes(self, text: str) -> str:
        """Normalize quote characters."""
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        return text
    
    def _normalize_dashes(self, text: str) -> str:
        """Normalize dash characters."""
        text = text.replace('–', '-').replace('—', '-')
        return text
    
    def _normalize_currencies(self, text: str) -> str:
        """Normalize currency representations."""
        for old, new in self.CURRENCY_MAP.items():
            text = text.replace(old, new)
        return text
    
    def _collapse_whitespace(self, text: str) -> str:
        """Collapse all whitespace to single spaces."""
        return re.sub(r'\s+', ' ', text)
    
    def is_substantive_text(self, text: str) -> bool:
        """Check if text contains substantive regulatory content."""
        text = text.strip()
        if len(text) < 10:
            return False
        
        # Filter out purely numeric or purely whitespace
        if re.match(r'^[\d\s.,-]+$', text):
            return False
        
        # Filter out standalone page numbers or section numbers
        if re.match(r'^\d+$', text):
            return False
        
        return True
    
    def extract_sentences(self, text: str) -> list[str]:
        """Split text into sentences for fine-grained comparison."""
        # Handle common abbreviations in RBI documents
        text = re.sub(r'\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|vs|etc|viz|i\.e|e\.g)\.',
                      r'\1<DOT>', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(No|nos|Sl|Ref|Sec|Ch|Art|Cl|Para|Sub)\.',
                      r'\1<DOT>', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(RBI|SEBI|NABARD|IRDAI|NHB|PFRDA)\.',
                      r'\1<DOT>', text, flags=re.IGNORECASE)
        
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z(])', text)
        
        # Restore dots
        sentences = [s.replace('<DOT>', '.') for s in sentences]
        
        return [s.strip() for s in sentences if s.strip()]
