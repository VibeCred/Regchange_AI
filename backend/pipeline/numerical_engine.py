"""
RegChange AI — Numerical Change Detection Engine
Extracts and compares monetary amounts, percentages, dates, durations,
thresholds, and limits from regulatory text.
"""
import re
import logging
from typing import Optional
from backend.models.change import NumericalChange

logger = logging.getLogger(__name__)


class NumericalEngine:
    """Deterministic numerical change detection."""
    
    # Monetary amount patterns
    MONEY_PATTERNS = [
        # INR / Rs. / ₹ amounts with crore/lakh
        re.compile(
            r'(?:₹|Rs\.?|INR|Rupees)\s*'
            r'(\d+(?:,\d+)*(?:\.\d+)?)\s*'
            r'(crore|crores|lakh|lakhs|thousand|million|billion)?',
            re.IGNORECASE
        ),
        # Amounts with crore/lakh first
        re.compile(
            r'(\d+(?:,\d+)*(?:\.\d+)?)\s*'
            r'(crore|crores|lakh|lakhs)\b',
            re.IGNORECASE
        ),
    ]
    
    # Percentage patterns
    PERCENTAGE_PATTERNS = [
        re.compile(r'(\d+(?:\.\d+)?)\s*(?:per\s*cent|percent|%)', re.IGNORECASE),
        re.compile(r'(\d+(?:\.\d+)?)\s*p\.c\.', re.IGNORECASE),
    ]
    
    # Duration patterns
    DURATION_PATTERNS = [
        re.compile(r'(?:within\s+)?(\d+)\s*(days?|months?|years?|weeks?|hours?)', re.IGNORECASE),
        re.compile(r'(\d+)\s*(?:calendar|working|business)\s*(days?|months?)', re.IGNORECASE),
        re.compile(r'(?:period\s+of\s+)(\d+)\s*(days?|months?|years?)', re.IGNORECASE),
    ]
    
    # Date patterns
    DATE_PATTERNS = [
        re.compile(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', re.IGNORECASE),
        re.compile(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', re.IGNORECASE),
        re.compile(r'(\d{2})[./](\d{2})[./](\d{4})'),
        re.compile(r'(\d{4})-(\d{2})-(\d{2})'),
    ]
    
    # Threshold/limit patterns
    LIMIT_PATTERNS = [
        re.compile(r'(?:minimum|min\.?)\s+(?:of\s+)?(?:₹|Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', re.IGNORECASE),
        re.compile(r'(?:maximum|max\.?)\s+(?:of\s+)?(?:₹|Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', re.IGNORECASE),
        re.compile(r'(?:not\s+(?:exceeding|exceed|more\s+than))\s+(?:₹|Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', re.IGNORECASE),
        re.compile(r'(?:at\s+least|not\s+less\s+than)\s+(?:₹|Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', re.IGNORECASE),
    ]
    
    # Multipliers
    MULTIPLIERS = {
        'crore': 10_000_000,
        'crores': 10_000_000,
        'lakh': 100_000,
        'lakhs': 100_000,
        'thousand': 1_000,
        'million': 1_000_000,
        'billion': 1_000_000_000,
    }
    
    def detect_numerical_changes(self, old_text: str, new_text: str) -> list[NumericalChange]:
        """
        Compare two texts and detect all numerical changes.
        Returns list of NumericalChange objects.
        """
        changes = []
        
        # Extract and compare monetary amounts
        old_amounts = self._extract_monetary(old_text)
        new_amounts = self._extract_monetary(new_text)
        changes.extend(self._compare_values(old_amounts, new_amounts, "monetary"))
        
        # Extract and compare percentages
        old_pcts = self._extract_percentages(old_text)
        new_pcts = self._extract_percentages(new_text)
        changes.extend(self._compare_values(old_pcts, new_pcts, "percentage"))
        
        # Extract and compare durations
        old_durations = self._extract_durations(old_text)
        new_durations = self._extract_durations(new_text)
        changes.extend(self._compare_values(old_durations, new_durations, "duration"))
        
        # Extract and compare dates
        old_dates = self._extract_dates(old_text)
        new_dates = self._extract_dates(new_text)
        if old_dates != new_dates:
            for od in old_dates:
                for nd in new_dates:
                    if od != nd:
                        changes.append(NumericalChange(
                            field="date",
                            old_value=od,
                            new_value=nd,
                            unit="date",
                            direction="CHANGED",
                        ))
        
        return changes
    
    def _extract_monetary(self, text: str) -> list[dict]:
        """Extract monetary amounts from text."""
        amounts = []
        for pattern in self.MONEY_PATTERNS:
            for match in pattern.finditer(text):
                value_str = match.group(1).replace(',', '')
                multiplier_str = match.group(2) if match.lastindex >= 2 and match.group(2) else ""
                
                try:
                    value = float(value_str)
                    multiplier = self.MULTIPLIERS.get(multiplier_str.lower(), 1) if multiplier_str else 1
                    numeric = value * multiplier
                    
                    amounts.append({
                        'text': match.group(0).strip(),
                        'value': numeric,
                        'unit': multiplier_str or 'INR',
                        'context': text[max(0, match.start()-30):match.end()+30],
                    })
                except ValueError:
                    pass
        
        return amounts
    
    def _extract_percentages(self, text: str) -> list[dict]:
        """Extract percentage values from text."""
        percentages = []
        for pattern in self.PERCENTAGE_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    value = float(match.group(1))
                    percentages.append({
                        'text': match.group(0).strip(),
                        'value': value,
                        'unit': '%',
                        'context': text[max(0, match.start()-30):match.end()+30],
                    })
                except ValueError:
                    pass
        
        return percentages
    
    def _extract_durations(self, text: str) -> list[dict]:
        """Extract duration values from text."""
        durations = []
        for pattern in self.DURATION_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    value = float(match.group(1))
                    unit = match.group(2).lower().rstrip('s')  # normalize: days->day
                    durations.append({
                        'text': match.group(0).strip(),
                        'value': value,
                        'unit': unit,
                        'context': text[max(0, match.start()-30):match.end()+30],
                    })
                except ValueError:
                    pass
        
        return durations
    
    def _extract_dates(self, text: str) -> list[str]:
        """Extract dates from text."""
        dates = []
        for pattern in self.DATE_PATTERNS:
            for match in pattern.finditer(text):
                dates.append(match.group(0).strip())
        return dates
    
    def _compare_values(
        self, 
        old_values: list[dict], 
        new_values: list[dict],
        field_type: str,
    ) -> list[NumericalChange]:
        """Compare extracted numerical values between old and new text."""
        changes = []
        
        # Match by context similarity or by position
        old_matched = set()
        new_matched = set()
        
        # Try to match by similar context
        for i, old_val in enumerate(old_values):
            best_match = None
            best_context_sim = 0
            
            for j, new_val in enumerate(new_values):
                if j in new_matched:
                    continue
                
                # Same unit?
                if old_val['unit'] != new_val['unit']:
                    continue
                
                # Context similarity
                from difflib import SequenceMatcher
                ctx_sim = SequenceMatcher(
                    None, 
                    old_val.get('context', '').lower(), 
                    new_val.get('context', '').lower()
                ).ratio()
                
                if ctx_sim > best_context_sim:
                    best_context_sim = ctx_sim
                    best_match = j
            
            if best_match is not None and best_context_sim > 0.3:
                new_val = new_values[best_match]
                
                if old_val['value'] != new_val['value']:
                    direction = "INCREASE" if new_val['value'] > old_val['value'] else "DECREASE"
                    magnitude = None
                    if old_val['value'] != 0:
                        magnitude = abs((new_val['value'] - old_val['value']) / old_val['value'] * 100)
                    
                    changes.append(NumericalChange(
                        field=field_type,
                        old_value=old_val['text'],
                        new_value=new_val['text'],
                        old_numeric=old_val['value'],
                        new_numeric=new_val['value'],
                        unit=old_val['unit'],
                        direction=direction,
                        magnitude_percent=magnitude,
                    ))
                
                old_matched.add(i)
                new_matched.add(best_match)
        
        # Unmatched old values = potentially removed
        # Unmatched new values = potentially added
        # (These are handled at the clause level, not here)
        
        return changes
    
    def extract_all_numbers(self, text: str) -> dict:
        """Extract all numerical values from text for comparison."""
        return {
            'monetary': self._extract_monetary(text),
            'percentages': self._extract_percentages(text),
            'durations': self._extract_durations(text),
            'dates': self._extract_dates(text),
        }
