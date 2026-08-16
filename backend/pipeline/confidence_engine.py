"""
RegChange AI — Confidence Engine
Multi-signal confidence scoring for change detection.
"""
import logging
from backend.models.change import ChangeRecord, ChangeType, ConfidenceBreakdown

logger = logging.getLogger(__name__)


class ConfidenceEngine:
    """Calculate multi-signal confidence scores."""
    
    # Weights for overall confidence
    WEIGHTS = {
        'structural_match': 0.20,
        'lexical_similarity': 0.25,
        'semantic_similarity': 0.25,
        'numerical_agreement': 0.15,
        'evidence_quality': 0.15,
    }
    
    def compute(self, change: ChangeRecord) -> float:
        """Recompute confidence for a change record."""
        conf = change.confidence
        
        # For added/removed, confidence is simpler
        if change.change_type in (ChangeType.ADDED, ChangeType.REMOVED):
            conf.overall = max(0.85, conf.evidence_quality)
            return conf.overall
        
        # Weighted combination
        overall = (
            conf.structural_match * self.WEIGHTS['structural_match'] +
            conf.lexical_similarity * self.WEIGHTS['lexical_similarity'] +
            conf.semantic_similarity * self.WEIGHTS['semantic_similarity'] +
            conf.numerical_agreement * self.WEIGHTS['numerical_agreement'] +
            conf.evidence_quality * self.WEIGHTS['evidence_quality']
        )
        
        # Boost if multiple signals agree
        high_signals = sum(1 for v in [
            conf.structural_match, conf.lexical_similarity,
            conf.semantic_similarity
        ] if v > 0.7)
        
        if high_signals >= 2:
            overall = min(1.0, overall + 0.05)
        
        # Penalty for very low signals
        if conf.structural_match < 0.2 and conf.semantic_similarity < 0.3:
            overall *= 0.8
        
        conf.overall = max(0.0, min(1.0, overall))
        return conf.overall
    
    def compute_all(self, changes: list[ChangeRecord]) -> list[ChangeRecord]:
        """Recompute confidence for all changes."""
        for change in changes:
            self.compute(change)
        return changes
