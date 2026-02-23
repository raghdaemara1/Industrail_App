import os
from dotenv import load_dotenv

load_dotenv()

# APP
DEFAULT_MACHINE = os.getenv("DEFAULT_MACHINE", "KHS_Filler")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
EXTRACTION_VERSION = os.getenv("EXTRACTION_VERSION", "v4-parameter-noise-filter")

# MONGODB
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "o3sigma_demo")

# PDF PARSING
PDF_PARSER = os.getenv("PDF_PARSER", "pdfplumber")

# LLM: CLASSIFICATION
REASON_CLASSIFICATION_MODE = os.getenv("REASON_CLASSIFICATION_MODE", "groq") # Using groq as requested for better API
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "my-llama-31-gguf:latest")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# LLM: EXTRACTION
ALARM_LLM_EXTRACTION = os.getenv("ALARM_LLM_EXTRACTION", "false").lower() == "true"
PARAMETER_LLM_ENRICHMENT = os.getenv("PARAMETER_LLM_ENRICHMENT", "false").lower() == "true"

# FILE STORAGE
FILE_STORAGE_BACKEND = os.getenv("FILE_STORAGE_BACKEND", "local")
FILE_STORAGE_DIR = os.getenv("FILE_STORAGE_DIR", "./pdf_store")

# SEARCH LAYER
SEARCH_BACKEND = os.getenv("SEARCH_BACKEND", "memory")

# VECTOR SEARCH
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "chromadb")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# GRAPH
GRAPH_BACKEND = os.getenv("GRAPH_BACKEND", "neo4j") # neo4j fallback networkx handling will be implemented in graph_index.py
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# ANALYTICS
ANALYTICS_BACKEND = os.getenv("ANALYTICS_BACKEND", "local")

# Constants
REASON_LEVEL_1_CATEGORIES = [
    "Automation, Process and Specialized Alarms",
    "Basic Machine and Safety Faults",
    "Rinser, Capper and Advanced Safety"
]

PARAMETER_NOISE_PATTERNS = [
    r"(?i)cause:",
    r"(?i)reaction:",
    r"(?i)remedy:"
]
