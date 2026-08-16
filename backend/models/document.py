"""
RegChange AI — Document Data Models
Pydantic models for document structure representation.
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ContentType(str, Enum):
    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"
    CLAUSE = "clause"
    SUB_CLAUSE = "sub_clause"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    ANNEXURE = "annexure"
    INTRODUCTION = "introduction"
    DEFINITION = "definition"
    HEADER = "header"
    FOOTER = "footer"
    UNKNOWN = "unknown"


class DocumentVersion(str, Enum):
    OLD = "old"
    NEW = "new"


class DocumentMetadata(BaseModel):
    """Top-level document metadata."""
    document_id: str
    filename: str
    title: str = ""
    circular_number: str = ""
    issue_date: str = ""
    update_date: str = ""
    total_pages: int = 0
    version: DocumentVersion = DocumentVersion.OLD
    quality_score: float = 1.0


class DocumentNode(BaseModel):
    """A single node in the hierarchical document tree."""
    node_id: str
    document_id: str
    document_version: DocumentVersion
    page_start: int
    page_end: int
    section_number: str = ""
    heading: str = ""
    parent_id: Optional[str] = None
    text: str = ""
    normalized_text: str = ""
    content_type: ContentType = ContentType.PARAGRAPH
    depth: int = 0  # 0=root, 1=chapter, 2=section, etc.
    order: int = 0  # position among siblings
    children_ids: list[str] = Field(default_factory=list)
    
    # Provenance
    raw_text: str = ""  # original text before normalization
    font_info: dict = Field(default_factory=dict)
    
    # For table nodes
    table_data: Optional[list[list[str]]] = None


class ParsedDocument(BaseModel):
    """Complete parsed document with hierarchy."""
    metadata: DocumentMetadata
    nodes: list[DocumentNode] = Field(default_factory=list)
    root_ids: list[str] = Field(default_factory=list)  # top-level node IDs
    
    def get_node(self, node_id: str) -> Optional[DocumentNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None
    
    def get_children(self, node_id: str) -> list[DocumentNode]:
        """Get children of a node."""
        node = self.get_node(node_id)
        if not node:
            return []
        return [n for n in self.nodes if n.node_id in node.children_ids]
    
    def get_leaf_nodes(self) -> list[DocumentNode]:
        """Get all leaf nodes (no children) — these are the comparison units."""
        return [n for n in self.nodes 
                if not n.children_ids 
                and n.content_type not in (ContentType.HEADER, ContentType.FOOTER)]
    
    def get_sections(self) -> list[DocumentNode]:
        """Get all section-level nodes."""
        return [n for n in self.nodes 
                if n.content_type in (
                    ContentType.CHAPTER, ContentType.SECTION, 
                    ContentType.SUBSECTION, ContentType.ANNEXURE
                )]
    
    def get_clauses(self) -> list[DocumentNode]:
        """Get all clause-level and paragraph-level nodes for comparison."""
        return [n for n in self.nodes 
                if n.content_type in (
                    ContentType.CLAUSE, ContentType.SUB_CLAUSE,
                    ContentType.PARAGRAPH, ContentType.DEFINITION
                ) and len(n.text.strip()) > 10]
