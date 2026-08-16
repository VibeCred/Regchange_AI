"""
RegChange AI — Obligation Strength Analyzer
Detects changes in regulatory obligation language (shall/must/may/etc.).
"""
import re
import logging
from backend.models.change import ObligationChange, ObligationDirection
from backend.config import OBLIGATION_STRENGTH

logger = logging.getLogger(__name__)


class ObligationAnalyzer:
    """Analyze changes in regulatory obligation strength."""
    
    # Multi-word terms must be checked before single-word terms
    OBLIGATION_TERMS_ORDERED = [
        'shall not', 'must not', 'not permitted', 'not allowed',
        'shall', 'must', 'required', 'mandatory', 'obligatory',
        'prohibited', 'forbidden',
        'should', 'expected', 'necessary',
        'recommended',
        'may', 'can', 'permitted', 'allowed', 'optional',
    ]
    
    # Context patterns that modify obligation meaning
    CONDITIONAL_PATTERNS = [
        re.compile(r'provided\s+that', re.IGNORECASE),
        re.compile(r'subject\s+to', re.IGNORECASE),
        re.compile(r'unless\s+otherwise', re.IGNORECASE),
        re.compile(r'except\s+where', re.IGNORECASE),
        re.compile(r'in\s+case\s+of', re.IGNORECASE),
        re.compile(r'notwithstanding', re.IGNORECASE),
    ]
    
    def analyze(self, old_text: str, new_text: str) -> ObligationChange:
        """
        Compare obligation strength between old and new text.
        
        Returns ObligationChange with direction and explanation.
        """
        old_terms = self._extract_obligation_terms(old_text)
        new_terms = self._extract_obligation_terms(new_text)
        
        old_strength = self._calculate_max_strength(old_terms)
        new_strength = self._calculate_max_strength(new_terms)
        
        # Determine direction
        direction = ObligationDirection.UNCHANGED
        explanation = ""
        
        if not old_terms and new_terms:
            direction = ObligationDirection.INTRODUCED
            explanation = f"New obligation language introduced: {', '.join(new_terms)}"
        elif old_terms and not new_terms:
            direction = ObligationDirection.REMOVED
            explanation = f"Obligation language removed: {', '.join(old_terms)}"
        elif old_strength < new_strength:
            direction = ObligationDirection.STRENGTHENED
            explanation = (
                f"Obligation strengthened from '{', '.join(old_terms)}' "
                f"to '{', '.join(new_terms)}'"
            )
        elif old_strength > new_strength:
            direction = ObligationDirection.RELAXED
            explanation = (
                f"Obligation relaxed from '{', '.join(old_terms)}' "
                f"to '{', '.join(new_terms)}'"
            )
        else:
            # Same strength but different terms?
            if set(old_terms) != set(new_terms):
                explanation = (
                    f"Obligation language changed from '{', '.join(old_terms)}' "
                    f"to '{', '.join(new_terms)}' (same strength level)"
                )
        
        # Check for conditional changes
        old_conditionals = self._extract_conditionals(old_text)
        new_conditionals = self._extract_conditionals(new_text)
        
        if old_conditionals != new_conditionals:
            added_cond = set(new_conditionals) - set(old_conditionals)
            removed_cond = set(old_conditionals) - set(new_conditionals)
            
            if added_cond:
                explanation += f" New conditions added: {', '.join(added_cond)}."
            if removed_cond:
                explanation += f" Conditions removed: {', '.join(removed_cond)}."
        
        return ObligationChange(
            old_terms=old_terms,
            new_terms=new_terms,
            old_strength=old_strength,
            new_strength=new_strength,
            direction=direction,
            explanation=explanation,
        )
    
    def _extract_obligation_terms(self, text: str) -> list[str]:
        """Extract obligation terms found in text."""
        text_lower = text.lower()
        found = []
        
        # Check multi-word terms first
        for term in self.OBLIGATION_TERMS_ORDERED:
            if term in text_lower:
                # Verify it's not part of a quoted or nested context
                pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
                if pattern.search(text):
                    found.append(term)
        
        # Remove duplicates preserving order
        seen = set()
        unique = []
        for t in found:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        
        return unique
    
    def _calculate_max_strength(self, terms: list[str]) -> int:
        """Calculate maximum obligation strength from terms."""
        if not terms:
            return 0
        
        strengths = [OBLIGATION_STRENGTH.get(t, 0) for t in terms]
        return max(strengths) if strengths else 0
    
    def _extract_conditionals(self, text: str) -> list[str]:
        """Extract conditional/qualifying phrases."""
        conditionals = []
        for pattern in self.CONDITIONAL_PATTERNS:
            if pattern.search(text):
                conditionals.append(pattern.pattern.replace(r'\s+', ' '))
        return conditionals
