import hashlib


def stable_point_id(document_id: str, chunk_index: int) -> int:
    """Create a deterministic positive Qdrant point ID."""
    digest = hashlib.sha256(f"{document_id}:{chunk_index}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFFFFFFFFFF
