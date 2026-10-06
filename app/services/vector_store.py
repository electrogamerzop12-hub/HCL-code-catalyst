"""
app/services/vector_store.py
===============================================================================
Vector Store Service (ChromaDB + HuggingFace sentence-transformers).

Manages persistent ChromaDB vector storage, embedding generation using 
all-MiniLM-L6-v2, chunk upserting, similarity searches, and healthchecks.
===============================================================================
"""

import os
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions
from app.config import settings


class VectorStoreService:
    """
    Service layer interacting with persistent ChromaDB vector store.
    """

    def __init__(self):
        """
        Initializes ChromaDB persistent client and sentence-transformers embedding function.
        """
        # Ensure disk storage directory exists
        os.makedirs(settings.CHROMADB_DIR, exist_ok=True)
        
        # Initialize persistent disk client
        self.client = chromadb.PersistentClient(path=settings.CHROMADB_DIR)

        # Initialize HuggingFace SentenceTransformer embedding function (384 dimensions)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL_NAME
        )

        # Get or create persistent collection with Cosine similarity space
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Generates embeddings and inserts/upserts document chunks into ChromaDB.
        
        :param chunks: List of chunk dictionaries containing 'id', 'text', and 'metadata'.
        :return: Count of chunks successfully indexed.
        """
        if not chunks:
            return 0

        # Unpack chunk properties into parallel arrays required by ChromaDB API
        ids = [chunk["id"] for chunk in chunks]
        documents = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]

        # Use upsert to overwrite existing chunk IDs if a document is re-ingested
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        return len(ids)

    def query(self, query_text: str, n_results: int = 5, where_filter: Optional[Dict[str, Any]] = None):
        """
        Executes semantic similarity search on the vector collection.
        
        :param query_text: Natural language user query string.
        :param n_results: Maximum number of relevant chunks to retrieve.
        :param where_filter: Optional metadata filtering criteria.
        :return: Query results containing documents, metadatas, and distance scores.
        """
        kwargs = {
            "query_texts": [query_text],
            "n_results": n_results
        }
        if where_filter:
            kwargs["where"] = where_filter

        return self.collection.query(**kwargs)

    def is_healthy(self) -> bool:
        """
        Executes client heartbeat check to verify vector store responsiveness.
        
        :return: True if healthy, False if connection/database failure occurs.
        """
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False
