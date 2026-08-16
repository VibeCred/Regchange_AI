"""
RegChange AI — Deterministic Diff Engine
Word-level diff detection between aligned clause pairs.
Distinguishes substantive from editorial changes.
"""
import re
import difflib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DiffResult:
    """Result of comparing two text blocks."""
    def __init__(self):
        self.has_changes: bool = False
        self.is_substantive: bool = False
        self.added_words: list[str] = []
        self.removed_words: list[str] = []
        self.modified_segments: list[dict] = []  # {old, new, type}
        self.similarity_ratio: float = 1.0
        self.change_density: float = 0.0  # fraction of text that changed
        self.diff_ops: list[dict] = []  # detailed ops for UI highlighting


class DiffEngine:
    """Compute word-level diffs and classify changes."""
    
    # Patterns that indicate editorial-only changes
    EDITORIAL_ONLY_PATTERNS = [
        # Capitalization differences
        lambda old, new: old.lower() == new.lower(),
        # Whitespace differences
        lambda old, new: re.sub(r'\s+', ' ', old).strip() == re.sub(r'\s+', ' ', new).strip(),
        # Punctuation-only differences
        lambda old, new: re.sub(r'[^\w\s]', '', old) == re.sub(r'[^\w\s]', '', new),
    ]
    
    # Words/phrases that indicate substantive regulatory content
    SUBSTANTIVE_INDICATORS = [
        'shall', 'must', 'required', 'mandatory', 'prohibited',
        'not permitted', 'may', 'should', 'permitted',
        'within', 'days', 'months', 'years',
        'percent', '%', 'lakh', 'crore', 'lakhs', 'crores',
        'penalty', 'fine', 'action', 'revoke', 'cancel',
        'eligible', 'exemption', 'exception', 'applicable',
        'report', 'submit', 'furnish', 'file',
        'effective', 'deadline', 'date', 'period',
        'minimum', 'maximum', 'limit', 'threshold',
    ]
    
    def compute_diff(self, old_text: str, new_text: str) -> DiffResult:
        """
        Compute detailed diff between old and new text.
        
        Returns DiffResult with:
        - Word-level changes
        - Substantive vs editorial classification
        - Similarity ratio
        - Diff operations for UI highlighting
        """
        result = DiffResult()
        
        if not old_text and not new_text:
            return result
        
        if old_text == new_text:
            result.similarity_ratio = 1.0
            return result
        
        result.has_changes = True
        
        # Word-level tokenization
        old_words = self._tokenize(old_text)
        new_words = self._tokenize(new_text)
        
        # Compute sequence matcher
        matcher = difflib.SequenceMatcher(None, old_words, new_words)
        result.similarity_ratio = matcher.ratio()
        
        # Get opcodes for detailed diff
        opcodes = matcher.get_opcodes()
        
        total_words = max(len(old_words), len(new_words), 1)
        changed_words = 0
        
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                result.diff_ops.append({
                    'type': 'equal',
                    'old_text': ' '.join(old_words[i1:i2]),
                    'new_text': ' '.join(new_words[j1:j2]),
                })
            elif tag == 'replace':
                old_segment = ' '.join(old_words[i1:i2])
                new_segment = ' '.join(new_words[j1:j2])
                result.diff_ops.append({
                    'type': 'replace',
                    'old_text': old_segment,
                    'new_text': new_segment,
                })
                result.modified_segments.append({
                    'old': old_segment,
                    'new': new_segment,
                    'type': 'replace',
                })
                changed_words += max(i2 - i1, j2 - j1)
            elif tag == 'delete':
                deleted = ' '.join(old_words[i1:i2])
                result.diff_ops.append({
                    'type': 'delete',
                    'old_text': deleted,
                    'new_text': '',
                })
                result.removed_words.extend(old_words[i1:i2])
                changed_words += i2 - i1
            elif tag == 'insert':
                inserted = ' '.join(new_words[j1:j2])
                result.diff_ops.append({
                    'type': 'insert',
                    'old_text': '',
                    'new_text': inserted,
                })
                result.added_words.extend(new_words[j1:j2])
                changed_words += j2 - j1
        
        result.change_density = changed_words / total_words
        
        # Determine if changes are substantive
        result.is_substantive = self._is_substantive(old_text, new_text, result)
        
        return result
    
    def _is_substantive(self, old_text: str, new_text: str, diff: DiffResult) -> bool:
        """
        Determine if the detected changes are substantive (regulatory impact)
        vs editorial (formatting, grammar, etc.).
        """
        # Check editorial-only patterns
        for pattern_fn in self.EDITORIAL_ONLY_PATTERNS:
            try:
                if pattern_fn(old_text, new_text):
                    return False
            except Exception:
                pass
        
        # If change density is very low and no substantive words changed
        if diff.change_density < 0.08:
            # Check if any substantive words were changed
            changed_text = ' '.join(
                seg['old'] + ' ' + seg['new'] 
                for seg in diff.modified_segments
            ).lower()
            changed_text += ' ' + ' '.join(diff.added_words).lower()
            changed_text += ' ' + ' '.join(diff.removed_words).lower()
            
            has_substantive = any(
                indicator in changed_text 
                for indicator in self.SUBSTANTIVE_INDICATORS
            )
            
            if not has_substantive:
                return False
        
        # Check each modified segment
        for segment in diff.modified_segments:
            old_seg = segment['old'].lower()
            new_seg = segment['new'].lower()
            
            # Pure capitalization change
            if old_seg == new_seg:
                continue
            
            # Check for numeric changes
            old_nums = re.findall(r'\d+(?:\.\d+)?', old_seg)
            new_nums = re.findall(r'\d+(?:\.\d+)?', new_seg)
            if old_nums != new_nums:
                return True
            
            # Check for obligation term changes
            for term in self.SUBSTANTIVE_INDICATORS:
                if (term in old_seg) != (term in new_seg):
                    return True
                if term in old_seg and term in new_seg:
                    # Same term present, check surrounding context
                    pass
        
        # If significant amount of text was added or removed
        if len(diff.added_words) > 10 or len(diff.removed_words) > 10:
            return True
        
        # If change density is moderate or higher
        if diff.change_density > 0.20:
            return True
        
        # Default: if similarity is below threshold, consider substantive
        if diff.similarity_ratio < 0.80:
            return True
        
        return False
    
    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into words for diffing."""
        # Split on whitespace but preserve punctuation attached to words
        return re.findall(r'\S+', text)
    
    def generate_html_diff(self, diff_result: DiffResult) -> dict:
        """Generate HTML-ready diff for the UI."""
        old_html_parts = []
        new_html_parts = []
        
        for op in diff_result.diff_ops:
            if op['type'] == 'equal':
                old_html_parts.append(op['old_text'])
                new_html_parts.append(op['new_text'])
            elif op['type'] == 'replace':
                old_html_parts.append(f'<span class="diff-removed">{op["old_text"]}</span>')
                new_html_parts.append(f'<span class="diff-added">{op["new_text"]}</span>')
            elif op['type'] == 'delete':
                old_html_parts.append(f'<span class="diff-removed">{op["old_text"]}</span>')
            elif op['type'] == 'insert':
                new_html_parts.append(f'<span class="diff-added">{op["new_text"]}</span>')
        
        return {
            'old_html': ' '.join(old_html_parts),
            'new_html': ' '.join(new_html_parts),
        }
