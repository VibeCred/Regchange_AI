"""
RegChange AI — Semantic Matcher
Uses sentence-transformers for embedding-based clause matching.
"""
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy-load to avoid slow startup
_model = None
_model_name = None


def get_model(model_name: str = "all-MiniLM-L6-v2"):
    """Lazy-load the embedding model."""
    global _model, _model_name
    if _model is None or _model_name != model_name:
        logger.info(f"Loading embedding model: {model_name}")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(model_name)
        _model_name = model_name
        logger.info(f"Embedding model loaded: {model_name}")
    return _model


class SemanticMatcher:
    """Compute semantic similarity between document clauses."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._embeddings_cache = {}
    
    def encode_texts(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Encode a list of texts into embeddings."""
        if not texts:
            return np.array([])
        
        model = get_model(self.model_name)
        
        # Check cache
        uncached_indices = []
        uncached_texts = []
        for i, text in enumerate(texts):
            if text not in self._embeddings_cache:
                uncached_indices.append(i)
                uncached_texts.append(text)
        
        # Encode uncached texts
        if uncached_texts:
            embeddings = model.encode(
                uncached_texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            for idx, text in enumerate(uncached_texts):
                self._embeddings_cache[text] = embeddings[idx]
        
        # Build result array
        result = np.zeros((len(texts), model.get_sentence_embedding_dimension()))
        for i, text in enumerate(texts):
            result[i] = self._embeddings_cache[text]
        
        return result
    
    def compute_similarity_matrix(
        self, 
        old_texts: list[str], 
        new_texts: list[str]
    ) -> np.ndarray:
        """
        Compute cosine similarity matrix between old and new clause texts.
        
        Returns:
            Matrix of shape (len(old_texts), len(new_texts))
            where [i][j] is the cosine similarity between old_texts[i] and new_texts[j]
        """
        if not old_texts or not new_texts:
            return np.array([])
        
        old_embeddings = self.encode_texts(old_texts)
        new_embeddings = self.encode_texts(new_texts)
        
        # Cosine similarity (embeddings are already normalized)
        similarity_matrix = np.dot(old_embeddings, new_embeddings.T)
        
        return similarity_matrix
    
    def compute_pairwise_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts."""
        embeddings = self.encode_texts([text1, text2])
        return float(np.dot(embeddings[0], embeddings[1]))
    
    def find_best_matches(
        self,
        old_texts: list[str],
        new_texts: list[str],
        threshold: float = 0.5,
        top_k: int = 3,
    ) -> list[dict]:
        """
        Find best semantic matches for each old text in new texts.
        
        Returns list of:
            {
                "old_idx": int,
                "new_idx": int,
                "similarity": float
            }
        """
        if not old_texts or not new_texts:
            return []
        
        sim_matrix = self.compute_similarity_matrix(old_texts, new_texts)
        
        matches = []
        for i in range(len(old_texts)):
            # Get top-k matches
            top_indices = np.argsort(sim_matrix[i])[::-1][:top_k]
            
            for j in top_indices:
                score = float(sim_matrix[i][j])
                if score >= threshold:
                    matches.append({
                        "old_idx": i,
                        "new_idx": int(j),
                        "similarity": score,
                    })
        
        return matches
