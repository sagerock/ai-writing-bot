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
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag_identity import stable_point_id

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
        parsed = urlparse(QDRANT_URL)
        host = parsed.hostname
        use_https = parsed.scheme == "https"

        # For internal Railway URLs (.railway.internal), use port 6333 and try gRPC
        if host and '.railway.internal' in host:
            port = 6333
            use_https = False  # Internal network uses HTTP
            # Try using gRPC for better performance on internal network
            try:
                self.qdrant = QdrantClient(
                    host=host,
                    grpc_port=6334,  # gRPC port
                    api_key=QDRANT_API_KEY,
                    timeout=60,
                    prefer_grpc=True,
                    https=False
                )
                print(f"Qdrant client initialized for {host}:6334 (gRPC)")
            except Exception as e:
                print(f"gRPC connection failed, falling back to REST: {e}")
                self.qdrant = QdrantClient(
                    host=host,
                    port=port,
                    api_key=QDRANT_API_KEY,
                    timeout=60,
                    prefer_grpc=False,
                    https=use_https
                )
                print(f"Qdrant client initialized for {host}:{port} (REST)")
        else:
            # For Railway public URLs (.up.railway.app), always use port 443
            if host and '.up.railway.app' in host:
                port = 443
                use_https = True
            else:
                port = parsed.port or (443 if use_https else 6333)

            self.qdrant = QdrantClient(
                host=host,
                port=port,
                api_key=QDRANT_API_KEY,
                timeout=60,
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
        project_name: str = "General",
        project_id: Optional[str] = None,
        source_id: Optional[str] = None,
        page_map: Optional[List[dict]] = None,
    ) -> int:
        """
        Index a document in Qdrant.

        Args:
            user_id: The user's unique ID
            filename: Name of the document
            text: Full text content of the document
            project_name: Project grouping for the document
            project_id: Stable project identifier for project-scoped retrieval
            source_id: Stable source identifier; avoids filename collisions
            page_map: Source offsets used to attach page/paragraph locations

        Returns:
            Number of chunks created
        """
        # Replace any prior version so shortened/re-uploaded files cannot leave
        # stale trailing chunks behind.
        self.delete_document(user_id, filename, document_key=source_id)

        # Split into chunks
        chunks = self.splitter.split_text(text)
        if not chunks:
            return 0

        # Get embeddings for all chunks
        embeddings = self._get_embeddings(chunks)

        # Create points for Qdrant
        document_id = f"{user_id}:{source_id or filename}"
        points = []
        previous_chunk_start = 0
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Python's built-in hash is randomized between processes. Use a stable
            # digest so re-indexing always addresses the same Qdrant points.
            point_id = stable_point_id(document_id, i)
            chunk_start = text.find(chunk, max(0, previous_chunk_start))
            if chunk_start < 0:
                chunk_start = text.find(chunk)
            if chunk_start < 0:
                chunk_start = previous_chunk_start
            previous_chunk_start = chunk_start + 1
            location = {}
            for entry in page_map or []:
                if entry.get("start", 0) <= chunk_start < entry.get("end", 0):
                    if "page" in entry:
                        location["page"] = entry["page"]
                    if "paragraph" in entry:
                        location["paragraph"] = entry["paragraph"]
                    break
            payload = {
                "user_id": user_id,
                "filename": filename,
                "project_name": project_name,
                "chunk_index": i,
                "chunk_text": chunk,
                "document_id": document_id,
                **location,
            }
            if project_id:
                payload["project_id"] = project_id
            if source_id:
                payload["source_id"] = source_id
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload,
            ))

        # Upsert to Qdrant with retry
        retry_on_timeout(lambda: self.qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        ))

        print(f"Indexed document '{filename}' for user {user_id}: {len(chunks)} chunks")
        return len(chunks)

    def delete_document(
        self,
        user_id: str,
        filename: str,
        document_key: Optional[str] = None,
    ):
        """Delete all chunks for a document from Qdrant."""
        document_id = f"{user_id}:{document_key or filename}"
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
                ),
                wait=True,
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
        project_name: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[dict]:
        """
        Search for relevant document chunks.

        Args:
            user_id: The user's unique ID
            query: Search query text
            top_k: Maximum number of results to return
            score_threshold: Minimum similarity score (0-1)
            project_name: Optional filter by project
            project_id: Optional stable project filter

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
        if project_id:
            filter_conditions.append(
                FieldCondition(
                    key="project_id",
                    match=MatchValue(value=project_id)
                )
            )

        # Search Qdrant and discard weak semantic matches.
        response = self.qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            query_filter=Filter(must=filter_conditions),
            limit=top_k,
            score_threshold=score_threshold,
        )
        results = response.points
        print(f"Qdrant search returned {len(results)} results")

        return [
            {
                "filename": r.payload["filename"],
                "chunk_text": r.payload["chunk_text"],
                "chunk_index": r.payload["chunk_index"],
                "score": r.score,
                "project_name": r.payload["project_name"],
                "project_id": r.payload.get("project_id"),
                "source_id": r.payload.get("source_id"),
                "page": r.payload.get("page"),
                "paragraph": r.payload.get("paragraph"),
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
                with_payload=["filename", "project_name", "source_id", "chunk_index"]
            )

            # Aggregate by document
            docs = {}
            for r in results:
                filename = r.payload["filename"]
                document_key = r.payload.get("source_id") or filename
                if document_key not in docs:
                    docs[document_key] = {
                        "filename": filename,
                        "project_name": r.payload["project_name"],
                        "source_id": r.payload.get("source_id"),
                        "chunk_count": 0
                    }
                docs[document_key]["chunk_count"] += 1

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
