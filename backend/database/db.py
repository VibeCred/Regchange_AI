"""
RegChange AI — SQLite Database Layer
Stores documents, comparisons, changes, and reviews.
"""
import sqlite3
import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional
from backend.config import DB_PATH

logger = logging.getLogger(__name__)


class Database:
    """SQLite database operations for RegChange AI."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    
    def _init_db(self):
        """Initialize database tables."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                title TEXT DEFAULT '',
                circular_number TEXT DEFAULT '',
                issue_date TEXT DEFAULT '',
                update_date TEXT DEFAULT '',
                total_pages INTEGER DEFAULT 0,
                version TEXT DEFAULT 'old',
                quality_score REAL DEFAULT 1.0,
                file_path TEXT DEFAULT '',
                parsed_data TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            );
            
            CREATE TABLE IF NOT EXISTS comparisons (
                comparison_id TEXT PRIMARY KEY,
                old_document_id TEXT NOT NULL,
                new_document_id TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                progress REAL DEFAULT 0.0,
                current_stage TEXT DEFAULT '',
                total_changes INTEGER DEFAULT 0,
                substantive_changes INTEGER DEFAULT 0,
                editorial_changes INTEGER DEFAULT 0,
                statistics TEXT DEFAULT '{}',
                llm_available INTEGER DEFAULT 0,
                error_message TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT,
                FOREIGN KEY (old_document_id) REFERENCES documents(document_id),
                FOREIGN KEY (new_document_id) REFERENCES documents(document_id)
            );
            
            CREATE TABLE IF NOT EXISTS changes (
                change_id TEXT PRIMARY KEY,
                comparison_id TEXT NOT NULL,
                change_type TEXT NOT NULL,
                category TEXT NOT NULL,
                sub_category TEXT DEFAULT '',
                is_substantive INTEGER DEFAULT 0,
                impact TEXT DEFAULT 'INFORMATIONAL',
                confidence_overall REAL DEFAULT 0.0,
                confidence_breakdown TEXT DEFAULT '{}',
                old_reference TEXT DEFAULT '{}',
                new_reference TEXT DEFAULT '{}',
                change_summary TEXT DEFAULT '',
                old_requirement TEXT DEFAULT '',
                new_requirement TEXT DEFAULT '',
                impact_explanation TEXT DEFAULT '',
                numerical_changes TEXT DEFAULT '[]',
                obligation_change TEXT DEFAULT '{}',
                evidence TEXT DEFAULT '[]',
                diff_highlights TEXT DEFAULT '[]',
                llm_classification TEXT DEFAULT '{}',
                llm_explanation TEXT DEFAULT '',
                llm_available INTEGER DEFAULT 0,
                prompt_version TEXT DEFAULT '',
                model_version TEXT DEFAULT '',
                review_status TEXT DEFAULT 'PENDING',
                reviewer_comment TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (comparison_id) REFERENCES comparisons(comparison_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_changes_comparison ON changes(comparison_id);
            CREATE INDEX IF NOT EXISTS idx_changes_category ON changes(category);
            CREATE INDEX IF NOT EXISTS idx_changes_impact ON changes(impact);
            CREATE INDEX IF NOT EXISTS idx_changes_substantive ON changes(is_substantive);
        """)
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def save_document(self, doc_data: dict):
        """Save document metadata."""
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO documents 
            (document_id, filename, title, circular_number, issue_date,
             total_pages, version, quality_score, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_data['document_id'],
            doc_data.get('filename', ''),
            doc_data.get('title', ''),
            doc_data.get('circular_number', ''),
            doc_data.get('issue_date', ''),
            doc_data.get('total_pages', 0),
            doc_data.get('version', 'old'),
            doc_data.get('quality_score', 1.0),
            doc_data.get('file_path', ''),
        ))
        conn.commit()
        conn.close()
    
    def save_comparison(self, comparison_data: dict):
        """Save or update comparison record."""
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO comparisons
            (comparison_id, old_document_id, new_document_id, status,
             progress, current_stage, total_changes, substantive_changes,
             editorial_changes, statistics, llm_available, error_message,
             created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            comparison_data['comparison_id'],
            comparison_data['old_document_id'],
            comparison_data['new_document_id'],
            comparison_data.get('status', 'pending'),
            comparison_data.get('progress', 0.0),
            comparison_data.get('current_stage', ''),
            comparison_data.get('total_changes', 0),
            comparison_data.get('substantive_changes', 0),
            comparison_data.get('editorial_changes', 0),
            json.dumps(comparison_data.get('statistics', {})),
            comparison_data.get('llm_available', False),
            comparison_data.get('error_message', ''),
            comparison_data.get('created_at', datetime.now(timezone.utc).isoformat()),
            comparison_data.get('completed_at', None),
        ))
        conn.commit()
        conn.close()
    
    def update_comparison_progress(self, comparison_id: str, progress: float, stage: str):
        """Update comparison progress."""
        conn = self._get_conn()
        conn.execute("""
            UPDATE comparisons SET progress = ?, current_stage = ? 
            WHERE comparison_id = ?
        """, (progress, stage, comparison_id))
        conn.commit()
        conn.close()
    
    def save_changes(self, changes: list[dict]):
        """Save change records in batch."""
        if not changes:
            return
        
        conn = self._get_conn()
        for change in changes:
            conn.execute("""
                INSERT OR REPLACE INTO changes
                (change_id, comparison_id, change_type, category, sub_category,
                 is_substantive, impact, confidence_overall, confidence_breakdown,
                 old_reference, new_reference, change_summary, old_requirement,
                 new_requirement, impact_explanation, numerical_changes,
                 obligation_change, evidence, diff_highlights, llm_classification,
                 llm_explanation, llm_available, prompt_version, model_version,
                 review_status, reviewer_comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                change['change_id'],
                change['comparison_id'],
                change['change_type'],
                change['category'],
                change.get('sub_category', ''),
                1 if change.get('is_substantive') else 0,
                change.get('impact', 'INFORMATIONAL'),
                change.get('confidence_overall', 0.0),
                json.dumps(change.get('confidence_breakdown', {})),
                json.dumps(change.get('old_reference', {})),
                json.dumps(change.get('new_reference', {})),
                change.get('change_summary', ''),
                change.get('old_requirement', ''),
                change.get('new_requirement', ''),
                change.get('impact_explanation', ''),
                json.dumps(change.get('numerical_changes', [])),
                json.dumps(change.get('obligation_change', {})),
                json.dumps(change.get('evidence', [])),
                json.dumps(change.get('diff_highlights', [])),
                json.dumps(change.get('llm_classification', {})),
                change.get('llm_explanation', ''),
                1 if change.get('llm_available') else 0,
                change.get('prompt_version', ''),
                change.get('model_version', ''),
                change.get('review_status', 'PENDING'),
                change.get('reviewer_comment', ''),
            ))
        conn.commit()
        conn.close()
        logger.info(f"Saved {len(changes)} change records")
    
    def get_comparison(self, comparison_id: str) -> Optional[dict]:
        """Get comparison by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM comparisons WHERE comparison_id = ?", (comparison_id,)
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    
    def get_changes(self, comparison_id: str, filters: dict = None) -> list[dict]:
        """Get changes for a comparison with optional filters."""
        conn = self._get_conn()
        query = "SELECT * FROM changes WHERE comparison_id = ?"
        params = [comparison_id]
        
        if filters:
            if filters.get('category'):
                query += " AND category = ?"
                params.append(filters['category'])
            if filters.get('impact'):
                query += " AND impact = ?"
                params.append(filters['impact'])
            if filters.get('is_substantive') is not None:
                query += " AND is_substantive = ?"
                params.append(1 if filters['is_substantive'] else 0)
            if filters.get('change_type'):
                query += " AND change_type = ?"
                params.append(filters['change_type'])
            if filters.get('review_status'):
                query += " AND review_status = ?"
                params.append(filters['review_status'])
        
        query += " ORDER BY CASE impact WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END"
        
        rows = conn.execute(query, params).fetchall()
        conn.close()
        
        results = []
        for row in rows:
            d = dict(row)
            # Parse JSON fields
            for field in ['confidence_breakdown', 'old_reference', 'new_reference',
                         'numerical_changes', 'obligation_change', 'evidence',
                         'diff_highlights', 'llm_classification', 'statistics']:
                if field in d and isinstance(d[field], str):
                    try:
                        d[field] = json.loads(d[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            results.append(d)
        
        return results
    
    def get_change(self, change_id: str) -> Optional[dict]:
        """Get a single change by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM changes WHERE change_id = ?", (change_id,)
        ).fetchone()
        conn.close()
        if row:
            d = dict(row)
            for field in ['confidence_breakdown', 'old_reference', 'new_reference',
                         'numerical_changes', 'obligation_change', 'evidence',
                         'diff_highlights', 'llm_classification']:
                if field in d and isinstance(d[field], str):
                    try:
                        d[field] = json.loads(d[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            return d
        return None
    
    def update_review(self, change_id: str, status: str, comment: str = ""):
        """Update review status of a change."""
        conn = self._get_conn()
        conn.execute("""
            UPDATE changes SET review_status = ?, reviewer_comment = ?
            WHERE change_id = ?
        """, (status, comment, change_id))
        conn.commit()
        conn.close()
    
    def get_statistics(self, comparison_id: str) -> dict:
        """Get aggregated statistics for a comparison."""
        conn = self._get_conn()
        
        stats = {}
        
        # Total counts
        row = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_substantive = 1 THEN 1 ELSE 0 END) as substantive,
                SUM(CASE WHEN is_substantive = 0 THEN 1 ELSE 0 END) as editorial,
                SUM(CASE WHEN change_type = 'ADDED' THEN 1 ELSE 0 END) as added,
                SUM(CASE WHEN change_type = 'REMOVED' THEN 1 ELSE 0 END) as removed,
                SUM(CASE WHEN change_type IN ('MODIFIED', 'REWORDED', 'RELOCATED') THEN 1 ELSE 0 END) as modified,
                SUM(CASE WHEN impact = 'CRITICAL' THEN 1 ELSE 0 END) as critical,
                SUM(CASE WHEN impact = 'HIGH' THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN impact = 'MEDIUM' THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN impact = 'LOW' THEN 1 ELSE 0 END) as low,
                SUM(CASE WHEN impact = 'INFORMATIONAL' THEN 1 ELSE 0 END) as informational,
                AVG(confidence_overall) as avg_confidence
            FROM changes WHERE comparison_id = ?
        """, (comparison_id,)).fetchone()
        
        if row:
            stats = dict(row)
        
        # Category distribution
        cat_rows = conn.execute("""
            SELECT category, COUNT(*) as count 
            FROM changes WHERE comparison_id = ? AND is_substantive = 1
            GROUP BY category ORDER BY count DESC
        """, (comparison_id,)).fetchall()
        
        stats['category_distribution'] = {r['category']: r['count'] for r in cat_rows}
        
        # Impact heatmap (category x impact)
        heatmap_rows = conn.execute("""
            SELECT category, impact, COUNT(*) as count
            FROM changes WHERE comparison_id = ? AND is_substantive = 1
            GROUP BY category, impact
        """, (comparison_id,)).fetchall()
        
        heatmap = {}
        for r in heatmap_rows:
            cat = r['category']
            if cat not in heatmap:
                heatmap[cat] = {}
            heatmap[cat][r['impact']] = r['count']
        stats['impact_heatmap'] = heatmap
        
        conn.close()
        return stats
    
    def list_comparisons(self) -> list[dict]:
        """List all comparisons."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM comparisons ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
