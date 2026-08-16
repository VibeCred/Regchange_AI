"""
RegChange AI — Multi-Layer Clause Alignment Engine
Aligns clauses between old and new documents using multiple strategies.
Supports one-to-one, one-to-many, many-to-one, added, removed.
"""
import re
import logging
import numpy as np
from difflib import SequenceMatcher
from collections import defaultdict
from typing import Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

from backend.models.document import DocumentNode, ParsedDocument, ContentType
from backend.pipeline.semantic_matcher import SemanticMatcher

logger = logging.getLogger(__name__)


class AlignmentType:
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    ADDED = "added"
    REMOVED = "removed"


class ClauseAlignment:
    """Result of aligning one or more old clauses to one or more new clauses."""
    def __init__(self):
        self.alignment_type: str = AlignmentType.ONE_TO_ONE
        self.old_nodes: list[DocumentNode] = []
        self.new_nodes: list[DocumentNode] = []
        self.confidence: float = 0.0
        self.match_method: str = ""  # exact, structural, lexical, semantic
        self.similarity_scores: dict = {}  # breakdown of scores
    
    def __repr__(self):
        old_ids = [n.section_number or n.node_id for n in self.old_nodes]
        new_ids = [n.section_number or n.node_id for n in self.new_nodes]
        return f"Alignment({self.alignment_type}: {old_ids} -> {new_ids}, conf={self.confidence:.2f})"


class ClauseAligner:
    """Multi-layer clause alignment engine."""
    
    # Weights for combining similarity scores
    WEIGHT_SECTION_NUM = 0.25
    WEIGHT_HEADING = 0.20
    WEIGHT_LEXICAL = 0.25
    WEIGHT_SEMANTIC = 0.30
    
    # Thresholds
    EXACT_MATCH_THRESHOLD = 0.95
    STRONG_MATCH_THRESHOLD = 0.70
    WEAK_MATCH_THRESHOLD = 0.50
    
    def __init__(self, use_semantic: bool = True):
        self.use_semantic = use_semantic
        self.semantic_matcher = SemanticMatcher() if use_semantic else None
    
    def align(
        self,
        old_doc: ParsedDocument,
        new_doc: ParsedDocument,
        progress_callback=None,
    ) -> list[ClauseAlignment]:
        """
        Align clauses between old and new documents.
        
        Returns a list of ClauseAlignment objects covering all clauses.
        """
        old_clauses = old_doc.get_clauses()
        new_clauses = new_doc.get_clauses()
        
        logger.info(f"Aligning {len(old_clauses)} old clauses with {len(new_clauses)} new clauses")
        
        if not old_clauses and not new_clauses:
            return []
        
        # Track matched indices
        old_matched = set()
        new_matched = set()
        alignments = []
        
        if progress_callback:
            progress_callback("clause_alignment", 0.1, "Starting exact matching...")
        
        # Layer 1: Exact section number + heading match
        exact_alignments = self._exact_match(old_clauses, new_clauses)
        for a in exact_alignments:
            for n in a.old_nodes:
                old_matched.add(old_clauses.index(n))
            for n in a.new_nodes:
                new_matched.add(new_clauses.index(n))
            alignments.append(a)
        
        logger.info(f"Layer 1 (Exact): {len(exact_alignments)} matches")
        
        if progress_callback:
            progress_callback("clause_alignment", 0.3, "Structural matching...")
        
        # Get remaining unmatched
        old_remaining = [(i, c) for i, c in enumerate(old_clauses) if i not in old_matched]
        new_remaining = [(i, c) for i, c in enumerate(new_clauses) if i not in new_matched]
        
        # Layer 2: Structural match (heading similarity)
        structural_alignments = self._structural_match(old_remaining, new_remaining)
        for a in structural_alignments:
            for n in a.old_nodes:
                idx = old_clauses.index(n)
                old_matched.add(idx)
            for n in a.new_nodes:
                idx = new_clauses.index(n)
                new_matched.add(idx)
            alignments.append(a)
        
        logger.info(f"Layer 2 (Structural): {len(structural_alignments)} matches")
        
        if progress_callback:
            progress_callback("clause_alignment", 0.5, "Lexical matching...")
        
        # Update remaining
        old_remaining = [(i, c) for i, c in enumerate(old_clauses) if i not in old_matched]
        new_remaining = [(i, c) for i, c in enumerate(new_clauses) if i not in new_matched]
        
        # Layer 3: Lexical similarity (TF-IDF)
        lexical_alignments = self._lexical_match(old_remaining, new_remaining)
        for a in lexical_alignments:
            for n in a.old_nodes:
                old_matched.add(old_clauses.index(n))
            for n in a.new_nodes:
                new_matched.add(new_clauses.index(n))
            alignments.append(a)
        
        logger.info(f"Layer 3 (Lexical): {len(lexical_alignments)} matches")
        
        if progress_callback:
            progress_callback("clause_alignment", 0.7, "Semantic matching...")
        
        # Update remaining
        old_remaining = [(i, c) for i, c in enumerate(old_clauses) if i not in old_matched]
        new_remaining = [(i, c) for i, c in enumerate(new_clauses) if i not in new_matched]
        
        # Layer 4: Semantic matching (embeddings)
        if self.use_semantic and old_remaining and new_remaining:
            semantic_alignments = self._semantic_match(old_remaining, new_remaining)
            for a in semantic_alignments:
                for n in a.old_nodes:
                    old_matched.add(old_clauses.index(n))
                for n in a.new_nodes:
                    new_matched.add(new_clauses.index(n))
                alignments.append(a)
            
            logger.info(f"Layer 4 (Semantic): {len(semantic_alignments)} matches")
        
        if progress_callback:
            progress_callback("clause_alignment", 0.9, "Identifying additions and removals...")
        
        # Remaining old = REMOVED
        for i, clause in enumerate(old_clauses):
            if i not in old_matched:
                a = ClauseAlignment()
                a.alignment_type = AlignmentType.REMOVED
                a.old_nodes = [clause]
                a.confidence = 0.9  # high confidence it was removed
                a.match_method = "unmatched"
                alignments.append(a)
        
        # Remaining new = ADDED
        for i, clause in enumerate(new_clauses):
            if i not in new_matched:
                a = ClauseAlignment()
                a.alignment_type = AlignmentType.ADDED
                a.new_nodes = [clause]
                a.confidence = 0.9
                a.match_method = "unmatched"
                alignments.append(a)
        
        if progress_callback:
            progress_callback("clause_alignment", 1.0, "Alignment complete")
        
        added = sum(1 for a in alignments if a.alignment_type == AlignmentType.ADDED)
        removed = sum(1 for a in alignments if a.alignment_type == AlignmentType.REMOVED)
        matched = sum(1 for a in alignments if a.alignment_type not in (AlignmentType.ADDED, AlignmentType.REMOVED))
        
        logger.info(
            f"Alignment complete: {matched} matched, {added} added, {removed} removed, "
            f"total {len(alignments)} alignments"
        )
        
        return alignments
    
    def _exact_match(
        self,
        old_clauses: list[DocumentNode],
        new_clauses: list[DocumentNode],
    ) -> list[ClauseAlignment]:
        """Layer 1: Match by exact section number + similar text."""
        alignments = []
        new_by_section = defaultdict(list)
        
        for clause in new_clauses:
            if clause.section_number:
                new_by_section[clause.section_number].append(clause)
        
        matched_new = set()
        
        for old_clause in old_clauses:
            if not old_clause.section_number:
                continue
            
            candidates = new_by_section.get(old_clause.section_number, [])
            
            for new_clause in candidates:
                if id(new_clause) in matched_new:
                    continue
                
                # Check text similarity
                text_sim = self._text_similarity(old_clause.normalized_text, new_clause.normalized_text)
                
                if text_sim >= 0.3:  # Even low similarity is OK if section numbers match exactly
                    a = ClauseAlignment()
                    a.alignment_type = AlignmentType.ONE_TO_ONE
                    a.old_nodes = [old_clause]
                    a.new_nodes = [new_clause]
                    a.confidence = min(1.0, 0.5 + text_sim * 0.5)
                    a.match_method = "exact"
                    a.similarity_scores = {
                        "section_match": 1.0,
                        "text_similarity": text_sim,
                    }
                    alignments.append(a)
                    matched_new.add(id(new_clause))
                    break
        
        return alignments
    
    def _structural_match(
        self,
        old_remaining: list[tuple[int, DocumentNode]],
        new_remaining: list[tuple[int, DocumentNode]],
    ) -> list[ClauseAlignment]:
        """Layer 2: Match by heading similarity (handles renumbered sections)."""
        alignments = []
        
        # Only consider nodes with headings
        old_with_headings = [(i, c) for i, c in old_remaining if c.heading]
        new_with_headings = [(i, c) for i, c in new_remaining if c.heading]
        
        if not old_with_headings or not new_with_headings:
            return alignments
        
        matched_new = set()
        
        for _, old_clause in old_with_headings:
            best_match = None
            best_score = 0.0
            
            for _, new_clause in new_with_headings:
                if id(new_clause) in matched_new:
                    continue
                
                # Compare headings
                heading_sim = self._text_similarity(
                    old_clause.heading.lower(),
                    new_clause.heading.lower()
                )
                
                if heading_sim >= 0.7:
                    # Also check text similarity
                    text_sim = self._text_similarity(
                        old_clause.normalized_text,
                        new_clause.normalized_text,
                    )
                    
                    combined = heading_sim * 0.6 + text_sim * 0.4
                    
                    if combined > best_score:
                        best_score = combined
                        best_match = new_clause
            
            if best_match and best_score >= 0.5:
                a = ClauseAlignment()
                a.alignment_type = AlignmentType.ONE_TO_ONE
                a.old_nodes = [old_clause]
                a.new_nodes = [best_match]
                a.confidence = best_score
                a.match_method = "structural"
                a.similarity_scores = {"structural_score": best_score}
                alignments.append(a)
                matched_new.add(id(best_match))
        
        return alignments
    
    def _lexical_match(
        self,
        old_remaining: list[tuple[int, DocumentNode]],
        new_remaining: list[tuple[int, DocumentNode]],
    ) -> list[ClauseAlignment]:
        """Layer 3: TF-IDF based lexical similarity matching."""
        if not old_remaining or not new_remaining:
            return []
        
        alignments = []
        
        old_texts = [c.normalized_text for _, c in old_remaining]
        new_texts = [c.normalized_text for _, c in new_remaining]
        
        # Filter out very short texts
        valid_old = [(i, t) for i, t in enumerate(old_texts) if len(t) > 20]
        valid_new = [(i, t) for i, t in enumerate(new_texts) if len(t) > 20]
        
        if not valid_old or not valid_new:
            return alignments
        
        all_texts = [t for _, t in valid_old] + [t for _, t in valid_new]
        
        try:
            vectorizer = TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                stop_words='english',
            )
            tfidf_matrix = vectorizer.fit_transform(all_texts)
            
            old_vectors = tfidf_matrix[:len(valid_old)]
            new_vectors = tfidf_matrix[len(valid_old):]
            
            sim_matrix = sklearn_cosine(old_vectors, new_vectors)
            
            matched_new = set()
            
            # Greedy best-first matching
            scores = []
            for i in range(len(valid_old)):
                for j in range(len(valid_new)):
                    if sim_matrix[i, j] >= self.WEAK_MATCH_THRESHOLD:
                        scores.append((sim_matrix[i, j], i, j))
            
            scores.sort(reverse=True)
            matched_old = set()
            
            for score, i, j in scores:
                if i in matched_old or j in matched_new:
                    continue
                
                old_orig_idx = valid_old[i][0]
                new_orig_idx = valid_new[j][0]
                
                old_clause = old_remaining[old_orig_idx][1]
                new_clause = new_remaining[new_orig_idx][1]
                
                a = ClauseAlignment()
                a.alignment_type = AlignmentType.ONE_TO_ONE
                a.old_nodes = [old_clause]
                a.new_nodes = [new_clause]
                a.confidence = float(score)
                a.match_method = "lexical"
                a.similarity_scores = {"tfidf_similarity": float(score)}
                alignments.append(a)
                
                matched_old.add(i)
                matched_new.add(j)
        
        except Exception as e:
            logger.warning(f"Lexical matching failed: {e}")
        
        return alignments
    
    def _semantic_match(
        self,
        old_remaining: list[tuple[int, DocumentNode]],
        new_remaining: list[tuple[int, DocumentNode]],
    ) -> list[ClauseAlignment]:
        """Layer 4: Embedding-based semantic matching."""
        if not old_remaining or not new_remaining:
            return []
        
        alignments = []
        
        old_texts = [c.text[:512] for _, c in old_remaining]  # truncate for efficiency
        new_texts = [c.text[:512] for _, c in new_remaining]
        
        try:
            sim_matrix = self.semantic_matcher.compute_similarity_matrix(old_texts, new_texts)
            
            if sim_matrix.size == 0:
                return alignments
            
            matched_new = set()
            matched_old = set()
            
            # Greedy best-first matching
            scores = []
            for i in range(len(old_texts)):
                for j in range(len(new_texts)):
                    if sim_matrix[i, j] >= self.WEAK_MATCH_THRESHOLD:
                        scores.append((sim_matrix[i, j], i, j))
            
            scores.sort(reverse=True)
            
            for score, i, j in scores:
                if i in matched_old or j in matched_new:
                    continue
                
                old_clause = old_remaining[i][1]
                new_clause = new_remaining[j][1]
                
                a = ClauseAlignment()
                a.alignment_type = AlignmentType.ONE_TO_ONE
                a.old_nodes = [old_clause]
                a.new_nodes = [new_clause]
                a.confidence = float(score)
                a.match_method = "semantic"
                a.similarity_scores = {"semantic_similarity": float(score)}
                alignments.append(a)
                
                matched_old.add(i)
                matched_new.add(j)
        
        except Exception as e:
            logger.warning(f"Semantic matching failed: {e}")
        
        return alignments
    
    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        """Compute text similarity using SequenceMatcher."""
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1, text2).ratio()
