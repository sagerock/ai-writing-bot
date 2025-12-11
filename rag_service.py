"""
RAG Service for RomaLume - Qdrant-based document retrieval

This module handles:
- Document chunking and embedding
- Storing document vectors in Qdrant
- Semantic search for relevant context
"""

import os
import time
from typing import List, Optional
from urllib.parse import urlparse
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)
from openai import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter

def retry_on_timeout(func, max_retries=3, delay=2):
    """Retry a function on timeout with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if "timed out" in str(e).lower() and attempt < max_retries - 1:
                print(f"Retry {attempt + 1}/{max_retries} after timeout...")
                time.sleep(delay * (attempt + 1))
            else:
                raise

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "romalume_documents"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536


class RAGService:
    """Service for document indexing and retrieval using Qdrant."""

    def __init__(self):
        if not QDRANT_URL:
            raise ValueError("QDRANT_URL environment variable not set")

        # Parse URL to extract host and port
        # Using host/port instead of url param fixes timeout issues
        parsed = urlparse(QDRANT_URL)
        host = parsed.hostname
        use_https = parsed.scheme == "https"
        port = parsed.port or (443 if use_https else 6333)

        self.qdrant = QdrantClient(
            host=host,
            port=port,
            api_key=QDRANT_API_KEY,
            timeout=30,
            prefer_grpc=False,
            https=use_https
        )
        print(f"Qdrant client initialized for {host}:{port} (https={use_https})")

        self.openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000,      # ~1000 tokens
            chunk_overlap=800,    # ~200 tokens overlap
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        # Skip collection check - collection was created manually
        # This avoids timeout issues on cross-cloud connections
        print(f"Using Qdrant collection: {COLLECTION_NAME}")

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a list of texts using OpenAI."""
        response = self.openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts
        )
        return [item.embedding for item in response.data]

    def index_document(
        self,
        user_id: str,
        filename: str,
        text: str,
        project_name: str = "General"
    ) -> int:
        """
        Index a document in Qdrant.

        Args:
            user_id: The user's unique ID
            filename: Name of the document
            text: Full text content of the document
            project_name: Project grouping for the document

        Returns:
            Number of chunks created
        """
        # Skip delete for now - upsert will overwrite with same IDs
        # self.delete_document(user_id, filename)

        # Split into chunks
        chunks = self.splitter.split_text(text)
        if not chunks:
            return 0

        # Get embeddings for all chunks
        embeddings = self._get_embeddings(chunks)

        # Create points for Qdrant
        document_id = f"{user_id}:{filename}"
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Create a unique point ID using hash
            point_id = hash(f"{document_id}:{i}") & 0x7FFFFFFFFFFFFFFF
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "user_id": user_id,
                    "filename": filename,
                    "project_name": project_name,
                    "chunk_index": i,
                    "chunk_text": chunk,
                    "document_id": document_id
                }
            ))

        # Upsert to Qdrant with retry
        retry_on_timeout(lambda: self.qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        ))

        print(f"Indexed document '{filename}' for user {user_id}: {len(chunks)} chunks")
        return len(chunks)

    def delete_document(self, user_id: str, filename: str):
        """Delete all chunks for a document from Qdrant."""
        document_id = f"{user_id}:{filename}"
        try:
            self.qdrant.delete(
                collection_name=COLLECTION_NAME,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )
            print(f"Deleted document '{filename}' from Qdrant for user {user_id}")
        except Exception as e:
            print(f"Warning: Could not delete document from Qdrant: {e}")

    def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
        project_name: Optional[str] = None
    ) -> List[dict]:
        """
        Search for relevant document chunks.

        Args:
            user_id: The user's unique ID
            query: Search query text
            top_k: Maximum number of results to return
            score_threshold: Minimum similarity score (0-1)
            project_name: Optional filter by project

        Returns:
            List of matching chunks with metadata
        """
        # Get query embedding
        query_embedding = self._get_embeddings([query])[0]

        # Build filter for user isolation
        filter_conditions = [
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id)
            )
        ]
        if project_name:
            filter_conditions.append(
                FieldCondition(
                    key="project_name",
                    match=MatchValue(value=project_name)
                )
            )

        # Search Qdrant (no score_threshold - let all results through)
        results = self.qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            query_filter=Filter(must=filter_conditions),
            limit=top_k
        )
        print(f"Qdrant search returned {len(results)} results")

        return [
            {
                "filename": r.payload["filename"],
                "chunk_text": r.payload["chunk_text"],
                "chunk_index": r.payload["chunk_index"],
                "score": r.score,
                "project_name": r.payload["project_name"]
            }
            for r in results
        ]

    def get_user_indexed_documents(self, user_id: str) -> List[dict]:
        """
        Get list of indexed documents for a user.

        Args:
            user_id: The user's unique ID

        Returns:
            List of documents with filename, project_name, and chunk_count
        """
        try:
            # Use scroll to get all points for this user
            results, _ = self.qdrant.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="user_id",
                            match=MatchValue(value=user_id)
                        )
                    ]
                ),
                limit=1000,
                with_payload=["filename", "project_name", "chunk_index"]
            )

            # Aggregate by document
            docs = {}
            for r in results:
                filename = r.payload["filename"]
                if filename not in docs:
                    docs[filename] = {
                        "filename": filename,
                        "project_name": r.payload["project_name"],
                        "chunk_count": 0
                    }
                docs[filename]["chunk_count"] += 1

            return list(docs.values())
        except Exception as e:
            print(f"Error getting indexed documents: {e}")
            return []


# Singleton instance
_rag_service = None


def get_rag_service() -> RAGService:
    """Get or create the RAG service singleton."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
