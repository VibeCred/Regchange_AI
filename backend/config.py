"""
RegChange AI — Configuration
"""
import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "regchange.db")

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# PDF Extraction
MAX_UPLOAD_SIZE_MB = 50
SUPPORTED_EXTENSIONS = {".pdf"}

# Structure Parser
CHAPTER_PATTERNS = [
    r'^CHAPTER\s+[IVXLCDM]+',
    r'^Chapter\s+[IVXLCDM]+',
    r'^CHAPTER\s+\d+',
    r'^Chapter\s+\d+',
]

SECTION_PATTERNS = [
    r'^(\d+)\.\s+',            # 1. Section title
    r'^(\d+\.\d+)\s+',         # 1.1 Subsection
    r'^(\d+\.\d+\.\d+)\s+',   # 1.1.1 Sub-subsection
]

CLAUSE_PATTERNS = [
    r'^\(([a-z])\)\s+',       # (a) clause
    r'^\(([ivxlcdm]+)\)\s+',  # (i) roman numeral clause
    r'^\((\d+)\)\s+',         # (1) numbered clause
    r'^([a-z])\.\s+',         # a. clause
    r'^([ivxlcdm]+)\.\s+',    # i. roman clause
]

ANNEXURE_PATTERNS = [
    r'^ANNEXURE\s+',
    r'^Annexure\s+',
    r'^ANNEX\s+',
    r'^Appendix\s+',
    r'^APPENDIX\s+',
    r'^Schedule\s+',
    r'^SCHEDULE\s+',
]

# Normalization
CURRENCY_EQUIVALENTS = {
    "₹": "INR",
    "Rs.": "INR",
    "Rs": "INR",
    "INR": "INR",
    "Rupees": "INR",
}

# Semantic Matching
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD_EXACT = 0.95
SIMILARITY_THRESHOLD_HIGH = 0.80
SIMILARITY_THRESHOLD_MEDIUM = 0.60
SIMILARITY_THRESHOLD_LOW = 0.40

# Alignment thresholds
ALIGNMENT_EXACT_MATCH = 0.95
ALIGNMENT_STRONG_MATCH = 0.75
ALIGNMENT_WEAK_MATCH = 0.50

# Obligation terms (ordered by strength)
OBLIGATION_MANDATORY = ["shall", "must", "required", "mandatory", "obligatory"]
OBLIGATION_STRONG = ["should", "expected", "necessary"]
OBLIGATION_PERMISSIVE = ["may", "can", "permitted", "allowed", "optional"]
OBLIGATION_PROHIBITIVE = ["shall not", "must not", "prohibited", "not permitted", "forbidden"]

OBLIGATION_STRENGTH = {
    "shall": 5,
    "must": 5,
    "required": 5,
    "mandatory": 5,
    "obligatory": 5,
    "shall not": 5,
    "must not": 5,
    "prohibited": 5,
    "not permitted": 5,
    "forbidden": 5,
    "should": 4,
    "expected": 4,
    "necessary": 4,
    "recommended": 3,
    "may": 2,
    "can": 2,
    "permitted": 2,
    "allowed": 2,
    "optional": 1,
}

# Change Categories
CHANGE_CATEGORIES = {
    "C01": "Added Requirement",
    "C02": "Removed Requirement",
    "C03": "Modified Requirement",
    "C04": "Threshold / Limit Change",
    "C05": "Timeline Change",
    "C06": "Eligibility Change",
    "C07": "Compliance Requirement",
    "C08": "Reporting Requirement",
    "C09": "Documentation Requirement",
    "C10": "Penalty / Consequence",
    "C11": "Scope Change",
    "C12": "Definition Change",
    "C13": "Exception / Exemption Change",
    "C14": "Procedural Change",
    "C15": "Reference / Cross-Reference Change",
    "C16": "Clarification",
    "C17": "Editorial Change",
}

# Impact Levels
IMPACT_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]

# LLM Configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2"
LLM_TIMEOUT = 120  # seconds
LLM_MAX_RETRIES = 2

# Confidence thresholds
CONFIDENCE_HIGH = 0.90
CONFIDENCE_MEDIUM = 0.70
CONFIDENCE_LOW = 0.50
HUMAN_REVIEW_THRESHOLD = 0.80

# API
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"
