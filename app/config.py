"""
app/config.py
===============================================================================
Configuration Management Module for the University Data Ingestion Pipeline.

This module loads environment variables (or defaults) for paths, vector stores,
database paths, chunking parameters, and external LLM endpoints (Ollama).
===============================================================================
"""

import os

# Gracefully import Pydantic BaseSettings if available, or fall back to standard class
try:
    from pydantic_settings import BaseSettings

    class Settings(BaseSettings):
        """Application settings with environment variable auto-loading."""
        
        APP_NAME: str = "University Student Services Data Ingestion Pipeline"
        DEBUG: bool = False

        # File system base directory calculations
        BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Data storage directory (SQLite DB & ChromaDB persistent vector store)
        DATA_DIR: str = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
        SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", os.path.join(DATA_DIR, "university.db"))
        CHROMADB_DIR: str = os.getenv("CHROMADB_DIR", os.path.join(DATA_DIR, "chromadb"))

        # HuggingFace Embedding Model Configuration
        EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
        CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "university_docs")

        # PDF Text Chunking parameters
        CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "600"))        # Target character count per chunk
        CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))   # Overlap between consecutive chunks

        # External LLM / Ollama & Cloud LLM Provider Endpoints
        OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")  # auto, ollama, bedrock, groq, openai, gemini
        LLM_MODEL: str = os.getenv("LLM_MODEL", "")
        
        # AWS Bedrock Mantle Settings
        BEDROCK_MANTLE_API_KEY: str = os.getenv("BEDROCK_MANTLE_API_KEY", "")
        BEDROCK_MANTLE_BASE_URL: str = os.getenv("BEDROCK_MANTLE_BASE_URL", "https://bedrock-mantle.ap-south-1.api.aws/v1")
        BEDROCK_MANTLE_MODEL: str = os.getenv("BEDROCK_MANTLE_MODEL", "google.gemma-3-27b-it")
        
        # Tavily Search API Key
        TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

        OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

        class Config:
            env_file = ".env"
            extra = "ignore"

except ImportError:
    # Fallback configuration class when pydantic_settings is not installed
    class Settings:
        """Fallback configuration class when pydantic_settings is not installed."""
        
        APP_NAME: str = "University Student Services Data Ingestion Pipeline"
        DEBUG: bool = False

        BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        DATA_DIR: str = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
        SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", os.path.join(DATA_DIR, "university.db"))
        CHROMADB_DIR: str = os.getenv("CHROMADB_DIR", os.path.join(DATA_DIR, "chromadb"))

        EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
        CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "university_docs")

        CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "600"))
        CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))

        OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")
        LLM_MODEL: str = os.getenv("LLM_MODEL", "")
        
        BEDROCK_MANTLE_API_KEY: str = os.getenv("BEDROCK_MANTLE_API_KEY", "")
        BEDROCK_MANTLE_BASE_URL: str = os.getenv("BEDROCK_MANTLE_BASE_URL", "https://bedrock-mantle.ap-south-1.api.aws/v1")
        BEDROCK_MANTLE_MODEL: str = os.getenv("BEDROCK_MANTLE_MODEL", "google.gemma-3-27b-it")
        TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

        OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

# Global singleton instance of application settings
settings = Settings()
