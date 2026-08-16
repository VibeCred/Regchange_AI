"""
RegChange AI — Impact Scorer
Deterministic impact level scoring for regulatory changes.
"""
import logging
from backend.models.change import (
    ChangeRecord, ChangeType, ChangeCategory, ImpactLevel,
    ObligationDirection
)

logger = logging.getLogger(__name__)


class ImpactScorer:
    """Score the operational impact of regulatory changes."""
    
    # Category base impact scores
    CATEGORY_BASE_IMPACT = {
        ChangeCategory.C01_ADDED_REQUIREMENT: 3,     # New requirement = generally high
        ChangeCategory.C02_REMOVED_REQUIREMENT: 3,
        ChangeCategory.C03_MODIFIED_REQUIREMENT: 2,
        ChangeCategory.C04_THRESHOLD_CHANGE: 3,
        ChangeCategory.C05_TIMELINE_CHANGE: 3,
        ChangeCategory.C06_ELIGIBILITY_CHANGE: 3,
        ChangeCategory.C07_COMPLIANCE_REQUIREMENT: 4,
        ChangeCategory.C08_REPORTING_REQUIREMENT: 3,
        ChangeCategory.C09_DOCUMENTATION_REQUIREMENT: 2,
        ChangeCategory.C10_PENALTY_CONSEQUENCE: 4,
        ChangeCategory.C11_SCOPE_CHANGE: 3,
        ChangeCategory.C12_DEFINITION_CHANGE: 2,
        ChangeCategory.C13_EXCEPTION_EXEMPTION: 3,
        ChangeCategory.C14_PROCEDURAL_CHANGE: 2,
        ChangeCategory.C15_REFERENCE_CHANGE: 1,
        ChangeCategory.C16_CLARIFICATION: 1,
        ChangeCategory.C17_EDITORIAL: 0,
    }
    
    def score(self, change: ChangeRecord) -> ImpactLevel:
        """
        Score the impact level of a change.
        Uses deterministic rules based on change characteristics.
        """
        if not change.is_substantive:
            return ImpactLevel.INFORMATIONAL
        
        score = self.CATEGORY_BASE_IMPACT.get(change.category, 1)
        
        # Obligation strengthening/relaxation
        if change.obligation_change:
            if change.obligation_change.direction == ObligationDirection.STRENGTHENED:
                score += 2
            elif change.obligation_change.direction == ObligationDirection.RELAXED:
                score += 1
            elif change.obligation_change.direction == ObligationDirection.INTRODUCED:
                score += 2
        
        # Numerical changes magnitude
        for nc in change.numerical_changes:
            if nc.magnitude_percent:
                if nc.magnitude_percent >= 100:
                    score += 2
                elif nc.magnitude_percent >= 50:
                    score += 1
            
            # Deadline shortening is high impact
            if nc.field == 'duration' and nc.direction == 'DECREASE':
                score += 1
        
        # Added content is generally important
        if change.change_type == ChangeType.ADDED:
            score += 1
        
        # Removed content can be critical
        if change.change_type == ChangeType.REMOVED:
            score += 1
        
        # Map score to impact level
        if score >= 6:
            return ImpactLevel.CRITICAL
        elif score >= 4:
            return ImpactLevel.HIGH
        elif score >= 3:
            return ImpactLevel.MEDIUM
        elif score >= 1:
            return ImpactLevel.LOW
        else:
            return ImpactLevel.INFORMATIONAL
    
    def score_all(self, changes: list[ChangeRecord]) -> list[ChangeRecord]:
        """Score all changes and update their impact levels."""
        for change in changes:
            change.impact = self.score(change)
        return changes
