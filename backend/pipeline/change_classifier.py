"""
RegChange AI — Change Classifier (Rule-Based)
Categorizes changes into C01-C17 taxonomy using deterministic rules.
"""
import re
import logging
from backend.models.change import (
    ChangeRecord, ChangeType, ChangeCategory, SourceReference,
    ConfidenceBreakdown
)
from backend.models.document import DocumentNode, ContentType
from backend.pipeline.clause_aligner import ClauseAlignment, AlignmentType
from backend.pipeline.diff_engine import DiffEngine, DiffResult
from backend.pipeline.numerical_engine import NumericalEngine
from backend.pipeline.obligation_analyzer import ObligationAnalyzer, ObligationChange
from backend.models.change import ObligationDirection

logger = logging.getLogger(__name__)


class ChangeClassifier:
    """Rule-based change classification into C01-C17 categories."""
    
    # Category detection patterns
    CATEGORY_PATTERNS = {
        ChangeCategory.C04_THRESHOLD_CHANGE: [
            re.compile(r'(?:₹|Rs\.?|INR|crore|lakh|percent|%)', re.IGNORECASE),
            re.compile(r'\b(?:threshold|limit|ceiling|floor|cap)\b', re.IGNORECASE),
        ],
        ChangeCategory.C05_TIMELINE_CHANGE: [
            re.compile(r'\b(?:within|deadline|due date|effective date|commencement)\b', re.IGNORECASE),
            re.compile(r'\b\d+\s*(?:days?|months?|years?|weeks?)\b', re.IGNORECASE),
            re.compile(r'\b(?:period|timeline|time.?frame|time.?limit)\b', re.IGNORECASE),
        ],
        ChangeCategory.C06_ELIGIBILITY_CHANGE: [
            re.compile(r'\b(?:eligible|eligibility|qualify|qualification|ineligible)\b', re.IGNORECASE),
            re.compile(r'\b(?:entitled|entitlement|disqualified)\b', re.IGNORECASE),
        ],
        ChangeCategory.C07_COMPLIANCE_REQUIREMENT: [
            re.compile(r'\b(?:comply|compliance|non.?compliance|adherence)\b', re.IGNORECASE),
            re.compile(r'\b(?:obligation|binding|compulsory)\b', re.IGNORECASE),
        ],
        ChangeCategory.C08_REPORTING_REQUIREMENT: [
            re.compile(r'\b(?:report|reporting|returns?|statement|submission|submit|furnish)\b', re.IGNORECASE),
            re.compile(r'\b(?:FIU|STR|CTR|suspicious transaction)\b', re.IGNORECASE),
        ],
        ChangeCategory.C09_DOCUMENTATION_REQUIREMENT: [
            re.compile(r'\b(?:document|documentation|records?|certificate|proof|evidence)\b', re.IGNORECASE),
            re.compile(r'\b(?:maintain|retention|preserve|keep)\b', re.IGNORECASE),
        ],
        ChangeCategory.C10_PENALTY_CONSEQUENCE: [
            re.compile(r'\b(?:penalty|penalt|fine|sanction|action|punish|revoke|cancel)\b', re.IGNORECASE),
            re.compile(r'\b(?:suspension|restriction|debarment|prohibition)\b', re.IGNORECASE),
        ],
        ChangeCategory.C11_SCOPE_CHANGE: [
            re.compile(r'\b(?:scope|applicability|applicable|coverage|extend|expand)\b', re.IGNORECASE),
            re.compile(r'\b(?:include|exclude|exempt|apply to)\b', re.IGNORECASE),
        ],
        ChangeCategory.C12_DEFINITION_CHANGE: [
            re.compile(r'\b(?:means?|defined|definition|shall include|refers? to)\b', re.IGNORECASE),
            re.compile(r'"[^"]+"', re.IGNORECASE),
        ],
        ChangeCategory.C13_EXCEPTION_EXEMPTION: [
            re.compile(r'\b(?:except|exception|exempt|exemption|waiver|relaxation)\b', re.IGNORECASE),
            re.compile(r'\b(?:provided that|notwithstanding|unless)\b', re.IGNORECASE),
        ],
        ChangeCategory.C14_PROCEDURAL_CHANGE: [
            re.compile(r'\b(?:procedure|process|method|mechanism|manner|mode)\b', re.IGNORECASE),
            re.compile(r'\b(?:steps?|stage|workflow|verification|validation)\b', re.IGNORECASE),
        ],
        ChangeCategory.C15_REFERENCE_CHANGE: [
            re.compile(r'\b(?:circular|direction|notification|regulation|act|rule|section)\b', re.IGNORECASE),
            re.compile(r'\b(?:refer|reference|pursuant|accordance|vide)\b', re.IGNORECASE),
            re.compile(r'RBI/\w+/\d+', re.IGNORECASE),
        ],
    }
    
    def __init__(self):
        self.diff_engine = DiffEngine()
        self.numerical_engine = NumericalEngine()
        self.obligation_analyzer = ObligationAnalyzer()
    
    def classify_alignment(
        self,
        alignment: ClauseAlignment,
        change_id: str,
        comparison_id: str = "",
    ) -> ChangeRecord:
        """
        Classify an alignment into a ChangeRecord.
        
        This is the main entry point for change classification.
        """
        # Handle ADDED
        if alignment.alignment_type == AlignmentType.ADDED:
            node = alignment.new_nodes[0]
            return ChangeRecord(
                change_id=change_id,
                comparison_id=comparison_id,
                change_type=ChangeType.ADDED,
                category=self._categorize_added(node),
                is_substantive=True,
                new_reference=self._make_reference(node),
                new_requirement=node.text[:500],
                change_summary=f"New content added: {node.heading or node.section_number or node.text[:80]}",
                evidence=[node.text[:300]],
                confidence=ConfidenceBreakdown(
                    structural_match=0.0,
                    lexical_similarity=0.0,
                    semantic_similarity=0.0,
                    evidence_quality=0.9,
                    overall=alignment.confidence,
                ),
            )
        
        # Handle REMOVED
        if alignment.alignment_type == AlignmentType.REMOVED:
            node = alignment.old_nodes[0]
            return ChangeRecord(
                change_id=change_id,
                comparison_id=comparison_id,
                change_type=ChangeType.REMOVED,
                category=ChangeCategory.C02_REMOVED_REQUIREMENT,
                is_substantive=True,
                old_reference=self._make_reference(node),
                old_requirement=node.text[:500],
                change_summary=f"Content removed: {node.heading or node.section_number or node.text[:80]}",
                evidence=[node.text[:300]],
                confidence=ConfidenceBreakdown(
                    structural_match=0.0,
                    lexical_similarity=0.0,
                    semantic_similarity=0.0,
                    evidence_quality=0.9,
                    overall=alignment.confidence,
                ),
            )
        
        # Handle matched pairs (ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE)
        old_node = alignment.old_nodes[0]
        new_node = alignment.new_nodes[0]
        
        old_text = old_node.text
        new_text = new_node.text
        
        # Compute diff
        diff_result = self.diff_engine.compute_diff(old_text, new_text)
        
        # If texts are identical, skip
        if not diff_result.has_changes:
            return ChangeRecord(
                change_id=change_id,
                comparison_id=comparison_id,
                change_type=ChangeType.UNCHANGED,
                category=ChangeCategory.C17_EDITORIAL,
                is_substantive=False,
                old_reference=self._make_reference(old_node),
                new_reference=self._make_reference(new_node),
                change_summary="No changes detected",
                confidence=ConfidenceBreakdown(
                    structural_match=alignment.similarity_scores.get('section_match', 0),
                    lexical_similarity=diff_result.similarity_ratio,
                    semantic_similarity=alignment.similarity_scores.get('semantic_similarity', 0),
                    evidence_quality=1.0,
                    overall=1.0,
                ),
            )
        
        # Detect numerical changes
        numerical_changes = self.numerical_engine.detect_numerical_changes(old_text, new_text)
        
        # Analyze obligation changes
        obligation_change = self.obligation_analyzer.analyze(old_text, new_text)
        
        # Determine change type
        change_type = self._determine_change_type(
            old_node, new_node, diff_result, alignment
        )
        
        # Determine category
        category = self._determine_category(
            old_text, new_text, diff_result,
            numerical_changes, obligation_change, old_node, new_node
        )
        
        # Determine if substantive
        is_substantive = self._is_substantive(
            diff_result, numerical_changes, obligation_change, category
        )
        
        # If not substantive, categorize as editorial
        if not is_substantive:
            category = ChangeCategory.C17_EDITORIAL
        
        # Generate diff highlights
        diff_html = self.diff_engine.generate_html_diff(diff_result)
        
        # Build change summary
        summary = self._generate_summary(
            change_type, category, old_node, new_node,
            diff_result, numerical_changes, obligation_change
        )
        
        # Build confidence
        confidence = ConfidenceBreakdown(
            structural_match=alignment.similarity_scores.get('section_match', 
                alignment.similarity_scores.get('structural_score', 0)),
            lexical_similarity=diff_result.similarity_ratio,
            semantic_similarity=alignment.similarity_scores.get('semantic_similarity',
                alignment.similarity_scores.get('tfidf_similarity', 0)),
            numerical_agreement=1.0 if not numerical_changes else 0.5,
            evidence_quality=0.9 if alignment.match_method in ('exact', 'structural') else 0.7,
            overall=alignment.confidence,
        )
        
        # Recompute overall confidence
        confidence.overall = (
            confidence.structural_match * 0.2 +
            confidence.lexical_similarity * 0.25 +
            confidence.semantic_similarity * 0.25 +
            confidence.numerical_agreement * 0.15 +
            confidence.evidence_quality * 0.15
        )
        # Ensure minimum from alignment
        confidence.overall = max(confidence.overall, alignment.confidence * 0.8)
        
        return ChangeRecord(
            change_id=change_id,
            comparison_id=comparison_id,
            change_type=change_type,
            category=category,
            is_substantive=is_substantive,
            old_reference=self._make_reference(old_node),
            new_reference=self._make_reference(new_node),
            change_summary=summary,
            old_requirement=old_text[:500],
            new_requirement=new_text[:500],
            numerical_changes=numerical_changes,
            obligation_change=obligation_change if obligation_change.direction != ObligationDirection.UNCHANGED else None,
            evidence=[old_text[:200], new_text[:200]],
            diff_highlights=[diff_html],
            confidence=confidence,
        )
    
    def _determine_change_type(
        self, old_node: DocumentNode, new_node: DocumentNode,
        diff: DiffResult, alignment: ClauseAlignment,
    ) -> ChangeType:
        """Determine the type of change."""
        # Check if section was relocated (different section number)
        if (old_node.section_number and new_node.section_number 
                and old_node.section_number != new_node.section_number):
            if diff.similarity_ratio > 0.9:
                return ChangeType.RELOCATED
        
        # Check if just reworded (high similarity, low substantive change)
        if diff.similarity_ratio > 0.8 and not diff.is_substantive:
            return ChangeType.REWORDED
        
        # Modified
        return ChangeType.MODIFIED
    
    def _determine_category(
        self, old_text: str, new_text: str,
        diff: DiffResult,
        numerical_changes: list,
        obligation_change: ObligationChange,
        old_node: DocumentNode,
        new_node: DocumentNode,
    ) -> ChangeCategory:
        """Determine the most appropriate change category."""
        # Priority-based category detection
        
        # Check if definition change
        if old_node.content_type == ContentType.DEFINITION or new_node.content_type == ContentType.DEFINITION:
            return ChangeCategory.C12_DEFINITION_CHANGE
        
        # Check for numerical changes first (highest priority)
        if numerical_changes:
            for nc in numerical_changes:
                if nc.field == 'monetary' or nc.field == 'percentage':
                    return ChangeCategory.C04_THRESHOLD_CHANGE
                if nc.field == 'duration':
                    return ChangeCategory.C05_TIMELINE_CHANGE
        
        # Check obligation changes
        if obligation_change.direction in (ObligationDirection.STRENGTHENED, ObligationDirection.RELAXED):
            return ChangeCategory.C07_COMPLIANCE_REQUIREMENT
        
        # Pattern-based detection on changed text
        changed_text = ' '.join(
            seg['old'] + ' ' + seg['new'] for seg in diff.modified_segments
        )
        changed_text += ' ' + ' '.join(diff.added_words)
        changed_text += ' ' + ' '.join(diff.removed_words)
        
        # Score each category
        category_scores = {}
        for category, patterns in self.CATEGORY_PATTERNS.items():
            score = 0
            for pattern in patterns:
                # Check in changed text
                if pattern.search(changed_text):
                    score += 2
                # Also check in full context
                if pattern.search(new_text):
                    score += 1
            category_scores[category] = score
        
        # Return highest scoring category
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            if category_scores[best_category] > 0:
                return best_category
        
        # Default
        return ChangeCategory.C03_MODIFIED_REQUIREMENT
    
    def _is_substantive(
        self, diff: DiffResult,
        numerical_changes: list,
        obligation_change: ObligationChange,
        category: ChangeCategory,
    ) -> bool:
        """Determine if the change is substantive."""
        # Numerical changes are always substantive
        if numerical_changes:
            return True
        
        # Obligation changes are always substantive
        if obligation_change.direction in (
            ObligationDirection.STRENGTHENED,
            ObligationDirection.RELAXED,
            ObligationDirection.INTRODUCED,
            ObligationDirection.REMOVED,
        ):
            return True
        
        # Editorial category = not substantive
        if category == ChangeCategory.C17_EDITORIAL:
            return False
        
        # Use diff engine's determination
        return diff.is_substantive
    
    def _categorize_added(self, node: DocumentNode) -> ChangeCategory:
        """Categorize an added node."""
        text = node.text.lower()
        
        # Check patterns
        for category, patterns in self.CATEGORY_PATTERNS.items():
            matches = sum(1 for p in patterns if p.search(text))
            if matches >= 2:
                return category
        
        if node.content_type == ContentType.DEFINITION:
            return ChangeCategory.C12_DEFINITION_CHANGE
        
        return ChangeCategory.C01_ADDED_REQUIREMENT
    
    def _make_reference(self, node: DocumentNode) -> SourceReference:
        """Create a SourceReference from a DocumentNode."""
        return SourceReference(
            document_id=node.document_id,
            page=node.page_start,
            page_end=node.page_end,
            section=node.section_number,
            clause=node.section_number,
            heading=node.heading,
            text=node.text[:500],
            node_id=node.node_id,
        )
    
    def _generate_summary(
        self, change_type: ChangeType, category: ChangeCategory,
        old_node: DocumentNode, new_node: DocumentNode,
        diff: DiffResult, numerical_changes: list,
        obligation_change: ObligationChange,
    ) -> str:
        """Generate a human-readable change summary."""
        parts = []
        
        # Location context
        old_loc = old_node.section_number or f"Page {old_node.page_start}"
        new_loc = new_node.section_number or f"Page {new_node.page_start}"
        
        if old_loc != new_loc:
            parts.append(f"Section {old_loc} -> {new_loc}.")
        
        # Change type
        from backend.config import CHANGE_CATEGORIES
        cat_name = CHANGE_CATEGORIES.get(category.value, category.value)
        parts.append(f"Category: {cat_name}.")
        
        # Numerical changes
        for nc in numerical_changes:
            parts.append(
                f"{nc.field.title()} changed: {nc.old_value} -> {nc.new_value} "
                f"({nc.direction}"
                f"{f', {nc.magnitude_percent:.0f}%' if nc.magnitude_percent else ''})"
            )
        
        # Obligation change
        if obligation_change.direction != ObligationDirection.UNCHANGED:
            parts.append(obligation_change.explanation)
        
        # Similarity
        if diff.similarity_ratio < 0.5:
            parts.append("Significant textual changes detected.")
        elif diff.similarity_ratio < 0.8:
            parts.append("Moderate textual changes detected.")
        
        return " ".join(parts)
