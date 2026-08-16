"""
RegChange AI — Change Record Models
Pydantic models for change detection results.
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ChangeType(str, Enum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    RELOCATED = "RELOCATED"
    REWORDED = "REWORDED"
    SPLIT = "SPLIT"          # one-to-many
    MERGED = "MERGED"        # many-to-one
    UNCHANGED = "UNCHANGED"


class ChangeCategory(str, Enum):
    C01_ADDED_REQUIREMENT = "C01"
    C02_REMOVED_REQUIREMENT = "C02"
    C03_MODIFIED_REQUIREMENT = "C03"
    C04_THRESHOLD_CHANGE = "C04"
    C05_TIMELINE_CHANGE = "C05"
    C06_ELIGIBILITY_CHANGE = "C06"
    C07_COMPLIANCE_REQUIREMENT = "C07"
    C08_REPORTING_REQUIREMENT = "C08"
    C09_DOCUMENTATION_REQUIREMENT = "C09"
    C10_PENALTY_CONSEQUENCE = "C10"
    C11_SCOPE_CHANGE = "C11"
    C12_DEFINITION_CHANGE = "C12"
    C13_EXCEPTION_EXEMPTION = "C13"
    C14_PROCEDURAL_CHANGE = "C14"
    C15_REFERENCE_CHANGE = "C15"
    C16_CLARIFICATION = "C16"
    C17_EDITORIAL = "C17"


class ImpactLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class ObligationDirection(str, Enum):
    STRENGTHENED = "STRENGTHENED"
    RELAXED = "RELAXED"
    UNCHANGED = "UNCHANGED"
    INTRODUCED = "INTRODUCED"
    REMOVED = "REMOVED"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EDITED = "EDITED"
    FLAGGED = "FLAGGED"


class SourceReference(BaseModel):
    """Reference to a specific location in a document."""
    document_id: str = ""
    page: int = 0
    page_end: int = 0
    section: str = ""
    clause: str = ""
    heading: str = ""
    text: str = ""
    node_id: str = ""


class NumericalChange(BaseModel):
    """Detected numerical change between versions."""
    field: str = ""  # what the number represents
    old_value: str = ""
    new_value: str = ""
    old_numeric: Optional[float] = None
    new_numeric: Optional[float] = None
    unit: str = ""
    direction: str = ""  # INCREASE, DECREASE
    magnitude_percent: Optional[float] = None


class ObligationChange(BaseModel):
    """Detected obligation strength change."""
    old_terms: list[str] = Field(default_factory=list)
    new_terms: list[str] = Field(default_factory=list)
    old_strength: int = 0
    new_strength: int = 0
    direction: ObligationDirection = ObligationDirection.UNCHANGED
    explanation: str = ""


class ConfidenceBreakdown(BaseModel):
    """Multi-signal confidence scoring."""
    structural_match: float = 0.0
    lexical_similarity: float = 0.0
    semantic_similarity: float = 0.0
    numerical_agreement: float = 1.0
    evidence_quality: float = 1.0
    overall: float = 0.0


class ChangeRecord(BaseModel):
    """Central data contract: one detected regulatory change."""
    change_id: str
    comparison_id: str = ""
    
    # Classification
    change_type: ChangeType
    category: ChangeCategory = ChangeCategory.C17_EDITORIAL
    sub_category: str = ""
    is_substantive: bool = False
    
    # Impact
    impact: ImpactLevel = ImpactLevel.INFORMATIONAL
    
    # Confidence
    confidence: ConfidenceBreakdown = Field(default_factory=ConfidenceBreakdown)
    
    # Source references
    old_reference: Optional[SourceReference] = None
    new_reference: Optional[SourceReference] = None
    
    # Change details
    change_summary: str = ""
    old_requirement: str = ""
    new_requirement: str = ""
    impact_explanation: str = ""
    
    # Detailed analysis
    numerical_changes: list[NumericalChange] = Field(default_factory=list)
    obligation_change: Optional[ObligationChange] = None
    
    # Evidence
    evidence: list[str] = Field(default_factory=list)
    diff_highlights: list[dict] = Field(default_factory=list)  # word-level diffs
    
    # LLM output (optional)
    llm_classification: Optional[dict] = None
    llm_explanation: str = ""
    llm_available: bool = False
    prompt_version: str = ""
    model_version: str = ""
    
    # Review
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewer_comment: str = ""
    
    # Metadata
    created_at: str = ""
    
    @property
    def needs_human_review(self) -> bool:
        """Check if this change should be flagged for human review."""
        return (
            self.confidence.overall < 0.80
            or self.impact in (ImpactLevel.CRITICAL, ImpactLevel.HIGH)
        )


class ComparisonResult(BaseModel):
    """Complete comparison result between two documents."""
    comparison_id: str
    old_document_id: str
    new_document_id: str
    
    # Results
    changes: list[ChangeRecord] = Field(default_factory=list)
    
    # Statistics
    total_changes: int = 0
    substantive_changes: int = 0
    editorial_changes: int = 0
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    
    # By impact
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    informational_count: int = 0
    
    # By category
    category_distribution: dict[str, int] = Field(default_factory=dict)
    
    # Quality
    old_doc_quality: float = 1.0
    new_doc_quality: float = 1.0
    overall_confidence: float = 0.0
    llm_available: bool = False
    
    # Status
    status: str = "pending"  # pending, processing, completed, failed
    progress: float = 0.0
    current_stage: str = ""
    error_message: str = ""
    
    created_at: str = ""
    completed_at: str = ""
    
    def compute_statistics(self):
        """Recompute statistics from changes list."""
        self.total_changes = len(self.changes)
        self.substantive_changes = sum(1 for c in self.changes if c.is_substantive)
        self.editorial_changes = sum(1 for c in self.changes if not c.is_substantive)
        self.added_count = sum(1 for c in self.changes if c.change_type == ChangeType.ADDED)
        self.removed_count = sum(1 for c in self.changes if c.change_type == ChangeType.REMOVED)
        self.modified_count = sum(1 for c in self.changes if c.change_type in (
            ChangeType.MODIFIED, ChangeType.REWORDED, ChangeType.RELOCATED
        ))
        
        self.critical_count = sum(1 for c in self.changes if c.impact == ImpactLevel.CRITICAL)
        self.high_count = sum(1 for c in self.changes if c.impact == ImpactLevel.HIGH)
        self.medium_count = sum(1 for c in self.changes if c.impact == ImpactLevel.MEDIUM)
        self.low_count = sum(1 for c in self.changes if c.impact == ImpactLevel.LOW)
        self.informational_count = sum(1 for c in self.changes if c.impact == ImpactLevel.INFORMATIONAL)
        
        # Category distribution
        self.category_distribution = {}
        for c in self.changes:
            cat = c.category.value
            self.category_distribution[cat] = self.category_distribution.get(cat, 0) + 1
        
        # Overall confidence
        if self.changes:
            self.overall_confidence = sum(c.confidence.overall for c in self.changes) / len(self.changes)
